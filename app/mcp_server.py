#!/usr/bin/env python3
"""
MCP Server for Whisperwynd Story Generator
4th Contribution: Integration test layer using MCP server interface
"""

import json
import time
import asyncio
from typing import Any, Dict, List
from datetime import datetime

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
from pydantic import BaseModel

# Import core functions from our Flask app
from app import (
    validate_request_data,
    process_image_request, 
    process_pdf_request,
    get_metrics,
    app_metrics,
    logger
)

# -------------------------------------------------------------------
# MCP SERVER SETUP
# -------------------------------------------------------------------
server = Server("whisperwynd-mcp")

class MCPRequest(BaseModel):
    request_id: str
    action: str
    payload: Dict[str, Any]

class MCPResponse(BaseModel):
    request_id: str
    status: str
    message: str
    data: Dict[str, Any] = {}
    metrics: Dict[str, Any] = {}
    timestamp: str

# -------------------------------------------------------------------
# MCP TOOLS
# -------------------------------------------------------------------

@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="validate_request",
            description="Validate request data structure and format",
            inputSchema={
                "type": "object",
                "properties": {
                    "request_data": {
                        "type": "object",
                        "description": "Request data to validate"
                    }
                },
                "required": ["request_data"]
            }
        ),
        Tool(
            name="process_image_generation",
            description="Process image generation request",
            inputSchema={
                "type": "object", 
                "properties": {
                    "request_id": {"type": "string"},
                    "prompt": {"type": "string"},
                    "width": {"type": "integer", "default": 512},
                    "height": {"type": "integer", "default": 512}
                },
                "required": ["request_id", "prompt"]
            }
        ),
        Tool(
            name="process_pdf_conversion",
            description="Process HTML to PDF conversion request",
            inputSchema={
                "type": "object",
                "properties": {
                    "request_id": {"type": "string"},
                    "html": {"type": "string"}
                },
                "required": ["request_id", "html"]
            }
        ),
        Tool(
            name="get_system_metrics",
            description="Get current system performance metrics",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="run_integration_test",
            description="Run full integration test with validation, processing, and metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_type": {
                        "type": "string",
                        "enum": ["image", "pdf", "both"],
                        "description": "Type of test to run"
                    },
                    "request_id": {"type": "string"},
                    "prompt": {"type": "string"},
                    "html": {"type": "string"}
                },
                "required": ["test_type", "request_id"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle MCP tool calls"""
    start_time = time.time()
    
    try:
        if name == "validate_request":
            request_data = arguments.get("request_data", {})
            is_valid, message = validate_request_data(request_data)
            
            response = MCPResponse(
                request_id=request_data.get("request_id", "unknown"),
                status="success" if is_valid else "error",
                message=message,
                data={"is_valid": is_valid},
                metrics=get_metrics(),
                timestamp=datetime.now().isoformat()
            )
            
        elif name == "process_image_generation":
            result = process_image_request(arguments)
            
            response = MCPResponse(
                request_id=arguments.get("request_id", "unknown"),
                status=result.get("status", "error"),
                message=result.get("message", "Unknown error"),
                data=result,
                metrics=get_metrics(),
                timestamp=datetime.now().isoformat()
            )
            
        elif name == "process_pdf_conversion":
            result = process_pdf_request(arguments)
            
            response = MCPResponse(
                request_id=arguments.get("request_id", "unknown"),
                status=result.get("status", "error"),
                message=result.get("message", "Unknown error"),
                data=result,
                metrics=get_metrics(),
                timestamp=datetime.now().isoformat()
            )
            
        elif name == "get_system_metrics":
            metrics = get_metrics()
            
            response = MCPResponse(
                request_id="metrics_request",
                status="success",
                message="Metrics retrieved successfully",
                data=metrics,
                metrics=metrics,
                timestamp=datetime.now().isoformat()
            )
            
        elif name == "run_integration_test":
            test_type = arguments.get("test_type")
            request_id = arguments.get("request_id")
            
            test_results = []
            
            # Run validation test
            is_valid, validation_msg = validate_request_data(arguments)
            test_results.append({
                "test": "validation",
                "status": "passed" if is_valid else "failed",
                "message": validation_msg
            })
            
            if is_valid:
                # Run processing tests based on type
                if test_type in ["image", "both"]:
                    if arguments.get("prompt"):
                        img_result = process_image_request(arguments)
                        test_results.append({
                            "test": "image_processing",
                            "status": "passed" if img_result.get("status") == "success" else "failed",
                            "message": img_result.get("message", "Unknown error"),
                            "data": img_result
                        })
                
                if test_type in ["pdf", "both"]:
                    if arguments.get("html"):
                        pdf_result = process_pdf_request(arguments)
                        test_results.append({
                            "test": "pdf_processing", 
                            "status": "passed" if pdf_result.get("status") == "success" else "failed",
                            "message": pdf_result.get("message", "Unknown error"),
                            "data": pdf_result
                        })
            
            # Calculate overall test status
            all_passed = all(test.get("status") == "passed" for test in test_results)
            
            response = MCPResponse(
                request_id=request_id,
                status="success" if all_passed else "partial_failure",
                message=f"Integration test completed - {len([t for t in test_results if t.get('status') == 'passed'])}/{len(test_results)} tests passed",
                data={
                    "test_results": test_results,
                    "overall_status": "passed" if all_passed else "failed"
                },
                metrics=get_metrics(),
                timestamp=datetime.now().isoformat()
            )
            
        else:
            response = MCPResponse(
                request_id="unknown",
                status="error",
                message=f"Unknown tool: {name}",
                data={},
                metrics={},
                timestamp=datetime.now().isoformat()
            )
        
        # Record performance metrics
        duration = time.time() - start_time
        app_metrics.record_response_time(duration, success=(response.status != "error"))
        
        # Log the MCP operation
        logger.info(f"MCP Tool '{name}' - Status: {response.status} - Duration: {duration:.3f}s")
        
        return [TextContent(
            type="text",
            text=json.dumps(response.dict(), indent=2)
        )]
        
    except Exception as e:
        duration = time.time() - start_time
        app_metrics.record_response_time(duration, success=False)
        app_metrics.record_error("MCP_ERROR", str(e))
        
        error_response = MCPResponse(
            request_id=arguments.get("request_id", "unknown"),
            status="error",
            message=f"MCP server error: {str(e)}",
            data={},
            metrics=get_metrics(),
            timestamp=datetime.now().isoformat()
        )
        
        logger.error(f"MCP Tool '{name}' failed - Duration: {duration:.3f}s - Error: {str(e)}")
        
        return [TextContent(
            type="text", 
            text=json.dumps(error_response.dict(), indent=2)
        )]

# -------------------------------------------------------------------
# MCP RESOURCES
# -------------------------------------------------------------------

@server.list_resources()
async def handle_list_resources() -> List[Resource]:
    """List available MCP resources"""
    return [
        Resource(
            uri="whisperwynd://metrics",
            name="System Metrics",
            description="Current application performance metrics",
            mimeType="application/json"
        ),
        Resource(
            uri="whisperwynd://health",
            name="Health Status", 
            description="Current system health and configuration status",
            mimeType="application/json"
        ),
        Resource(
            uri="whisperwynd://test-examples",
            name="Test Examples",
            description="Sample test requests for validation",
            mimeType="application/json"
        )
    ]

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read MCP resource content"""
    if uri == "whisperwynd://metrics":
        metrics = get_metrics()
        return json.dumps(metrics, indent=2)
        
    elif uri == "whisperwynd://health":
        health_data = {
            "service": "Whisperwynd MCP Server",
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "metrics_summary": {
                "total_requests": app_metrics.request_count,
                "success_rate": f"{(app_metrics.successful_generations / max(1, app_metrics.successful_generations + app_metrics.failed_generations) * 100):.1f}%"
            }
        }
        return json.dumps(health_data, indent=2)
        
    elif uri == "whisperwynd://test-examples":
        examples = {
            "image_generation_test": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "action": "generate_image",
                "payload": {
                    "prompt": "A mystical forest with glowing trees",
                    "width": 512,
                    "height": 512
                }
            },
            "pdf_conversion_test": {
                "request_id": "550e8400-e29b-41d4-a716-446655440001", 
                "action": "convert_pdf",
                "payload": {
                    "html": "<h1>Test Story</h1><p>Once upon a time in Whisperwynd...</p>"
                }
            },
            "integration_test": {
                "request_id": "550e8400-e29b-41d4-a716-446655440002",
                "action": "integration_test",
                "payload": {
                    "test_type": "both",
                    "prompt": "A dragon in the clouds",
                    "html": "<h1>Dragon Story</h1><p>The dragon soared through the misty clouds...</p>"
                }
            }
        }
        return json.dumps(examples, indent=2)
    
    else:
        raise ValueError(f"Unknown resource: {uri}")

# -------------------------------------------------------------------
# MAIN SERVER ENTRY POINT
# -------------------------------------------------------------------

async def main():
    """Main MCP server entry point"""
    logger.info("Starting Whisperwynd MCP Server...")
    
    # Initialize server options
    options = InitializationOptions(
        server_name="whisperwynd-mcp",
        server_version="1.0.0"
    )
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            options
        )

if __name__ == "__main__":
    print(" Whisperwynd MCP Server Starting...")
    print(" Integration test layer for validation, processing, and metrics")
    print(" Wraps existing Flask app logic for structured testing")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n MCP Server stopped by user")
    except Exception as e:
        print(f"MCP Server error: {e}")
        logger.error(f"MCP Server startup failed: {e}")
