#!/usr/bin/env python3
"""
Web-based MCP Server for Whisperwynd Story Generator
Provides localhost interface to test MCP functionality
"""

import json
import time
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

# Import core functions from our main app
from app import (
    validate_request_data,
    process_image_request,
    process_pdf_request,
    get_metrics,
    app_metrics,
    logger
)

# -------------------------------------------------------------------
# WEB MCP SERVER SETUP
# -------------------------------------------------------------------
mcp_app = Flask(__name__)

def generate_test_uuid():
    """Generate a valid UUID for testing"""
    return str(uuid.uuid4())

def create_mcp_response(request_id, status, message, data=None, metrics=None):
    """Create standardized MCP response"""
    return {
        "request_id": request_id,
        "status": status,
        "message": message,
        "data": data or {},
        "metrics": metrics or get_metrics(),
        "timestamp": datetime.now().isoformat()
    }

# -------------------------------------------------------------------
# WEB INTERFACE
# -------------------------------------------------------------------

MCP_INTERFACE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Whisperwynd MCP Server Interface</title>
    <style>
        * { box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container { 
            max-width: 1400px; 
            margin: 0 auto; 
        }
        .header { 
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            color: #2c3e50; 
            padding: 30px; 
            border-radius: 16px; 
            margin-bottom: 30px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            text-align: center;
        }
        .header h1 {
            margin: 0 0 10px 0;
            font-size: 2.5em;
            font-weight: 700;
            background: linear-gradient(45deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .header p {
            margin: 0;
            font-size: 1.1em;
            opacity: 0.8;
        }
        .tools-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }
        .tool-section { 
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 25px; 
            border-radius: 16px; 
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .tool-section:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 40px rgba(0,0,0,0.15);
        }
        .tool-title { 
            color: #2c3e50; 
            border-bottom: 3px solid #667eea;
            padding-bottom: 12px;
            margin-bottom: 20px;
            font-size: 1.3em;
            font-weight: 600;
        }
        .form-group { 
            margin: 18px 0; 
        }
        label { 
            display: block; 
            margin-bottom: 8px; 
            font-weight: 600;
            color: #34495e;
        }
        input, textarea, select { 
            width: 100%; 
            padding: 12px 16px; 
            border: 2px solid #e1e8ed;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }
        input:focus, textarea:focus, select:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        textarea { 
            height: 120px; 
            resize: vertical;
            font-family: 'Courier New', monospace;
        }
        button { 
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white; 
            padding: 12px 24px; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
            transition: all 0.2s ease;
            margin: 5px 5px 5px 0;
        }
        button:hover { 
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }
        button:active {
            transform: translateY(0);
        }
        .response { 
            background: #f8f9fa;
            border: 2px solid #e9ecef;
            padding: 20px; 
            border-radius: 12px; 
            margin-top: 20px;
            font-family: 'Segoe UI', sans-serif;
        }
        .response-header {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
            font-size: 1.1em;
            font-weight: 600;
        }
        .response-content {
            background: #ffffff;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            line-height: 1.5;
        }
        .metrics { 
            background: linear-gradient(135deg, #e8f5e8 0%, #f0f8f0 100%);
            border-left: 4px solid #27ae60; 
            padding: 20px; 
            margin: 20px 0;
            border-radius: 8px;
        }
        .error { 
            background: linear-gradient(135deg, #ffeaa7 0%, #fff2cc 100%);
            border-left: 4px solid #e17055; 
            padding: 20px;
            border-radius: 8px;
        }
        .success { 
            background: linear-gradient(135deg, #d5f4e6 0%, #e8f8f0 100%);
            border-left: 4px solid #00b894; 
            padding: 20px;
            border-radius: 8px;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            margin-right: 10px;
        }
        .status-success {
            background: #d5f4e6;
            color: #00b894;
        }
        .status-error {
            background: #ffeaa7;
            color: #e17055;
        }
        .uuid-group {
            display: flex;
            gap: 10px;
            align-items: flex-end;
        }
        .uuid-group input {
            flex: 1;
        }
        .uuid-group button {
            flex-shrink: 0;
            margin: 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Whisperwynd MCP Server</h1>
            <p>Model Context Protocol Integration Layer - Testing & Validation Dashboard</p>
            <p style="font-size: 0.9em; margin-top: 10px; opacity: 0.7;">Stdio-based MCP server for structured AI workflow testing</p>
        </div>

        <div class="tools-grid">

        <!-- Metrics Dashboard -->
        <div class="tool-section">
            <h2 class="tool-title"> System Metrics</h2>
            <button onclick="getMetrics()">Refresh Metrics</button>
            <div id="metrics-display" class="metrics">
                <p>Click "Refresh Metrics" to view current system performance</p>
            </div>
        </div>

        <!-- Request Validation Tool -->
        <div class="tool-section">
            <h2 class="tool-title"> Request Validation</h2>
            <div class="form-group">
                <label>Request ID:</label>
                <div class="uuid-group">
                    <input type="text" id="validate-id" placeholder="Auto-generated UUID">
                    <button onclick="generateUUID('validate-id')">Generate</button>
                </div>
            </div>
            <div class="form-group">
                <label>Prompt:</label>
                <input type="text" id="validate-prompt" placeholder="A mystical forest scene">
            </div>
            <button onclick="validateRequest()">Validate Request</button>
            <div id="validate-response" class="response" style="display:none;"></div>
        </div>

        <!-- Image Generation Tool -->
        <div class="tool-section">
            <h2 class="tool-title"> Image Generation Test</h2>
            <div class="form-group">
                <label>Request ID:</label>
                <div class="uuid-group">
                    <input type="text" id="image-id" placeholder="Auto-generated UUID">
                    <button onclick="generateUUID('image-id')">Generate</button>
                </div>
            </div>
            <div class="form-group">
                <label>Prompt:</label>
                <input type="text" id="image-prompt" placeholder="A dragon flying over Whisperwynd mountains">
            </div>
            <div class="form-group">
                <label>Width:</label>
                <input type="number" id="image-width" value="512">
            </div>
            <div class="form-group">
                <label>Height:</label>
                <input type="number" id="image-height" value="512">
            </div>
            <button onclick="processImage()">Process Image Request</button>
            <div id="image-response" class="response" style="display:none;"></div>
        </div>

        <!-- PDF Conversion Tool -->
        <div class="tool-section">
            <h2 class="tool-title"> PDF Conversion Test</h2>
            <div class="form-group">
                <label>Request ID:</label>
                <div class="uuid-group">
                    <input type="text" id="pdf-id" placeholder="Auto-generated UUID">
                    <button onclick="generateUUID('pdf-id')">Generate</button>
                </div>
            </div>
            <div class="form-group">
                <label>HTML Content:</label>
                <textarea id="pdf-html" placeholder="<h1>Test Story</h1><p>Once upon a time...</p>"></textarea>
            </div>
            <button onclick="processPDF()">Process PDF Request</button>
            <div id="pdf-response" class="response" style="display:none;"></div>
        </div>

        <!-- Integration Test Tool -->
        <div class="tool-section">
            <h2 class="tool-title"> Full Integration Test</h2>
            <div class="form-group">
                <label>Test Type:</label>
                <select id="integration-type">
                    <option value="image">Image Only</option>
                    <option value="pdf">PDF Only</option>
                    <option value="both">Both Image & PDF</option>
                </select>
            </div>
            <div class="form-group">
                <label>Request ID:</label>
                <div class="uuid-group">
                    <input type="text" id="integration-id" placeholder="Auto-generated UUID">
                    <button onclick="generateUUID('integration-id')">Generate</button>
                </div>
            </div>
            <div class="form-group">
                <label>Prompt (for image):</label>
                <input type="text" id="integration-prompt" placeholder="A magical library in the clouds">
            </div>
            <div class="form-group">
                <label>HTML (for PDF):</label>
                <textarea id="integration-html" placeholder="<h1>Integration Test</h1><p>Testing MCP server...</p>"></textarea>
            </div>
            <button onclick="runIntegrationTest()">Run Integration Test</button>
            <div id="integration-response" class="response" style="display:none;"></div>
        </div>
        </div>
    </div>

    <script>
        function generateUUID(inputId) {
            const uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                const r = Math.random() * 16 | 0;
                const v = c == 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
            document.getElementById(inputId).value = uuid;
        }

        async function makeRequest(endpoint, data) {
            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                return await response.json();
            } catch (error) {
                return {status: 'error', message: 'Network error: ' + error.message};
            }
        }

        function formatResponseText(response) {
            let output = [];
            
            // Basic info
            output.push(`Status: ${response.status}`);
            output.push(`Message: ${response.message}`);
            output.push(`Request ID: ${response.request_id}`);
            output.push(`Timestamp: ${new Date(response.timestamp).toLocaleString()}`);
            
            // Data section
            if (response.data && Object.keys(response.data).length > 0) {
                output.push('\n--- Response Data ---');
                for (const [key, value] of Object.entries(response.data)) {
                    if (key === 'test_results' && Array.isArray(value)) {
                        output.push(`${key}:`);
                        value.forEach((test, i) => {
                            output.push(`  Test ${i + 1}: ${test.test} - ${test.status}`);
                            output.push(`    Message: ${test.message}`);
                        });
                    } else if (typeof value === 'object') {
                        output.push(`${key}: ${JSON.stringify(value, null, 2)}`);
                    } else {
                        output.push(`${key}: ${value}`);
                    }
                }
            }
            
            // Metrics section
            if (response.metrics && Object.keys(response.metrics).length > 0) {
                output.push('\n--- System Metrics ---');
                for (const [key, value] of Object.entries(response.metrics)) {
                    output.push(`${key}: ${value}`);
                }
            }
            
            return output.join('\n');
        }

        function displayResponse(elementId, response) {
            const element = document.getElementById(elementId);
            const isSuccess = response.status === 'success' || response.status === 'validation_failed';
            element.className = `response ${isSuccess ? 'success' : 'error'}`;
            element.style.display = 'block';
            
            const statusBadge = isSuccess ? 
                '<span class="status-badge status-success">SUCCESS</span>' : 
                '<span class="status-badge status-error">ERROR</span>';
            
            element.innerHTML = `
                <div class="response-header">
                    ${statusBadge}
                    ${response.status.toUpperCase().replace('_', ' ')}
                </div>
                <div class="response-content">
                    ${formatResponseText(response)}
                </div>
            `;
        }

        async function getMetrics() {
            const response = await makeRequest('/mcp/metrics', {});
            const element = document.getElementById('metrics-display');
            
            if (response.status === 'success' && response.data) {
                const metrics = response.data;
                element.innerHTML = `
                    <h4>System Performance Metrics</h4>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 15px;">
                        <div style="background: white; padding: 15px; border-radius: 8px; text-align: center;">
                            <div style="font-size: 2em; font-weight: bold; color: #667eea;">${metrics.total_requests || 0}</div>
                            <div style="font-size: 0.9em; color: #666;">Total Requests</div>
                        </div>
                        <div style="background: white; padding: 15px; border-radius: 8px; text-align: center;">
                            <div style="font-size: 2em; font-weight: bold; color: #27ae60;">${metrics.success_rate || 'N/A'}</div>
                            <div style="font-size: 0.9em; color: #666;">Success Rate</div>
                        </div>
                        <div style="background: white; padding: 15px; border-radius: 8px; text-align: center;">
                            <div style="font-size: 2em; font-weight: bold; color: #764ba2;">${metrics.average_response_time || 'N/A'}</div>
                            <div style="font-size: 0.9em; color: #666;">Avg Response Time</div>
                        </div>
                        <div style="background: white; padding: 15px; border-radius: 8px; text-align: center;">
                            <div style="font-size: 2em; font-weight: bold; color: #e17055;">${metrics.uptime_formatted || 'N/A'}</div>
                            <div style="font-size: 0.9em; color: #666;">Uptime</div>
                        </div>
                    </div>
                    <div style="margin-top: 15px; font-size: 0.9em; color: #666;">
                        Last updated: ${new Date().toLocaleTimeString()}
                    </div>
                `;
            } else {
                element.innerHTML = `<p style="color: #e17055;">Failed to load metrics: ${response.message}</p>`;
            }
        }

        async function validateRequest() {
            const data = {
                request_id: document.getElementById('validate-id').value || generateTestUUID(),
                prompt: document.getElementById('validate-prompt').value
            };
            const response = await makeRequest('/mcp/validate', data);
            displayResponse('validate-response', response);
        }

        async function processImage() {
            const data = {
                request_id: document.getElementById('image-id').value || generateTestUUID(),
                prompt: document.getElementById('image-prompt').value,
                width: parseInt(document.getElementById('image-width').value),
                height: parseInt(document.getElementById('image-height').value)
            };
            const response = await makeRequest('/mcp/image', data);
            displayResponse('image-response', response);
        }

        async function processPDF() {
            const data = {
                request_id: document.getElementById('pdf-id').value || generateTestUUID(),
                html: document.getElementById('pdf-html').value
            };
            const response = await makeRequest('/mcp/pdf', data);
            displayResponse('pdf-response', response);
        }

        async function runIntegrationTest() {
            const data = {
                test_type: document.getElementById('integration-type').value,
                request_id: document.getElementById('integration-id').value || generateTestUUID(),
                prompt: document.getElementById('integration-prompt').value,
                html: document.getElementById('integration-html').value
            };
            const response = await makeRequest('/mcp/integration', data);
            displayResponse('integration-response', response);
        }

        function generateTestUUID() {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                const r = Math.random() * 16 | 0;
                const v = c == 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        }

        // Auto-load metrics on page load
        window.onload = function() {
            getMetrics();
        };
    </script>
</body>
</html>
"""

# -------------------------------------------------------------------
# WEB MCP ENDPOINTS
# -------------------------------------------------------------------

@mcp_app.route('/')
def mcp_interface():
    """MCP testing web interface"""
    return render_template_string(MCP_INTERFACE_HTML)

@mcp_app.route('/mcp/metrics', methods=['POST'])
def mcp_get_metrics():
    """Get system metrics via MCP interface"""
    start_time = time.time()
    try:
        metrics = get_metrics()
        duration = time.time() - start_time
        
        response = create_mcp_response(
            request_id="metrics_request",
            status="success", 
            message="Metrics retrieved successfully",
            data=metrics,
            metrics=metrics
        )
        
        logger.info(f"MCP Metrics request - Duration: {duration:.3f}s")
        return jsonify(response)
        
    except Exception as e:
        duration = time.time() - start_time
        app_metrics.record_error("MCP_METRICS_ERROR", str(e))
        
        response = create_mcp_response(
            request_id="metrics_request",
            status="error",
            message=f"Failed to get metrics: {str(e)}"
        )
        
        logger.error(f"MCP Metrics failed - Duration: {duration:.3f}s - Error: {str(e)}")
        return jsonify(response), 500

@mcp_app.route('/mcp/validate', methods=['POST'])
def mcp_validate():
    """Validate request via MCP interface"""
    start_time = time.time()
    data = request.get_json(force=True)
    
    try:
        is_valid, message = validate_request_data(data)
        duration = time.time() - start_time
        app_metrics.record_response_time(duration, success=is_valid)
        
        response = create_mcp_response(
            request_id=data.get("request_id", "unknown"),
            status="success" if is_valid else "validation_failed",
            message=message,
            data={"is_valid": is_valid, "validation_details": message}
        )
        
        logger.info(f"MCP Validation - Duration: {duration:.3f}s - Valid: {is_valid}")
        return jsonify(response)
        
    except Exception as e:
        duration = time.time() - start_time
        app_metrics.record_response_time(duration, success=False)
        app_metrics.record_error("MCP_VALIDATION_ERROR", str(e))
        
        response = create_mcp_response(
            request_id=data.get("request_id", "unknown"),
            status="error",
            message=f"Validation error: {str(e)}"
        )
        
        logger.error(f"MCP Validation failed - Duration: {duration:.3f}s - Error: {str(e)}")
        return jsonify(response), 500

@mcp_app.route('/mcp/image', methods=['POST'])
def mcp_process_image():
    """Process image generation via MCP interface"""
    start_time = time.time()
    data = request.get_json(force=True)
    
    try:
        # First validate
        is_valid, validation_msg = validate_request_data(data)
        if not is_valid:
            response = create_mcp_response(
                request_id=data.get("request_id", "unknown"),
                status="validation_failed",
                message=validation_msg
            )
            return jsonify(response), 400
        
        # Process image request
        result = process_image_request(data)
        duration = time.time() - start_time
        
        success = result.get("status") == "success"
        app_metrics.record_response_time(duration, success=success)
        
        response = create_mcp_response(
            request_id=data.get("request_id", "unknown"),
            status=result.get("status", "error"),
            message=result.get("message", "Unknown error"),
            data=result
        )
        
        logger.info(f"MCP Image Processing - Duration: {duration:.3f}s - Success: {success}")
        return jsonify(response)
        
    except Exception as e:
        duration = time.time() - start_time
        app_metrics.record_response_time(duration, success=False)
        app_metrics.record_error("MCP_IMAGE_ERROR", str(e))
        
        response = create_mcp_response(
            request_id=data.get("request_id", "unknown"),
            status="error",
            message=f"Image processing error: {str(e)}"
        )
        
        logger.error(f"MCP Image Processing failed - Duration: {duration:.3f}s - Error: {str(e)}")
        return jsonify(response), 500

@mcp_app.route('/mcp/pdf', methods=['POST'])
def mcp_process_pdf():
    """Process PDF conversion via MCP interface"""
    start_time = time.time()
    data = request.get_json(force=True)
    
    try:
        # First validate
        is_valid, validation_msg = validate_request_data(data)
        if not is_valid:
            response = create_mcp_response(
                request_id=data.get("request_id", "unknown"),
                status="validation_failed",
                message=validation_msg
            )
            return jsonify(response), 400
        
        # Process PDF request
        result = process_pdf_request(data)
        duration = time.time() - start_time
        
        success = result.get("status") == "success"
        app_metrics.record_response_time(duration, success=success)
        
        response = create_mcp_response(
            request_id=data.get("request_id", "unknown"),
            status=result.get("status", "error"),
            message=result.get("message", "Unknown error"),
            data=result
        )
        
        logger.info(f"MCP PDF Processing - Duration: {duration:.3f}s - Success: {success}")
        return jsonify(response)
        
    except Exception as e:
        duration = time.time() - start_time
        app_metrics.record_response_time(duration, success=False)
        app_metrics.record_error("MCP_PDF_ERROR", str(e))
        
        response = create_mcp_response(
            request_id=data.get("request_id", "unknown"),
            status="error",
            message=f"PDF processing error: {str(e)}"
        )
        
        logger.error(f"MCP PDF Processing failed - Duration: {duration:.3f}s - Error: {str(e)}")
        return jsonify(response), 500

@mcp_app.route('/mcp/integration', methods=['POST'])
def mcp_integration_test():
    """Run full integration test via MCP interface"""
    start_time = time.time()
    data = request.get_json(force=True)
    
    try:
        test_type = data.get("test_type", "both")
        request_id = data.get("request_id", generate_test_uuid())
        
        test_results = []
        
        # Step 1: Validation
        is_valid, validation_msg = validate_request_data(data)
        test_results.append({
            "test": "validation",
            "status": "passed" if is_valid else "failed",
            "message": validation_msg,
            "duration": "0.001s"
        })
        
        if is_valid:
            # Step 2: Image processing (if requested)
            if test_type in ["image", "both"] and data.get("prompt"):
                img_start = time.time()
                img_result = process_image_request(data)
                img_duration = time.time() - img_start
                
                test_results.append({
                    "test": "image_processing",
                    "status": "passed" if img_result.get("status") == "success" else "failed",
                    "message": img_result.get("message", "Unknown error"),
                    "duration": f"{img_duration:.3f}s",
                    "data": img_result
                })
            
            # Step 3: PDF processing (if requested)
            if test_type in ["pdf", "both"] and data.get("html"):
                pdf_start = time.time()
                pdf_result = process_pdf_request(data)
                pdf_duration = time.time() - pdf_start
                
                test_results.append({
                    "test": "pdf_processing",
                    "status": "passed" if pdf_result.get("status") == "success" else "failed", 
                    "message": pdf_result.get("message", "Unknown error"),
                    "duration": f"{pdf_duration:.3f}s",
                    "data": pdf_result
                })
        
        # Calculate results
        total_duration = time.time() - start_time
        passed_tests = len([t for t in test_results if t.get("status") == "passed"])
        total_tests = len(test_results)
        all_passed = passed_tests == total_tests
        
        app_metrics.record_response_time(total_duration, success=all_passed)
        
        response = create_mcp_response(
            request_id=request_id,
            status="success" if all_passed else "partial_failure",
            message=f"Integration test completed - {passed_tests}/{total_tests} tests passed",
            data={
                "test_results": test_results,
                "overall_status": "passed" if all_passed else "failed",
                "total_duration": f"{total_duration:.3f}s",
                "test_summary": {
                    "passed": passed_tests,
                    "total": total_tests,
                    "success_rate": f"{(passed_tests/total_tests*100):.1f}%"
                }
            }
        )
        
        logger.info(f"MCP Integration Test - Duration: {total_duration:.3f}s - Passed: {passed_tests}/{total_tests}")
        return jsonify(response)
        
    except Exception as e:
        duration = time.time() - start_time
        app_metrics.record_response_time(duration, success=False)
        app_metrics.record_error("MCP_INTEGRATION_ERROR", str(e))
        
        response = create_mcp_response(
            request_id=data.get("request_id", "unknown"),
            status="error",
            message=f"Integration test error: {str(e)}"
        )
        
        logger.error(f"MCP Integration Test failed - Duration: {duration:.3f}s - Error: {str(e)}")
        return jsonify(response), 500

# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
if __name__ == "__main__":
    print("Whisperwynd MCP Web Server Starting...")
    print(" Integration test layer accessible via web interface")
    print(" http://127.0.0.1:9000")
    print()
    
    logger.info("Starting Whisperwynd MCP Web Server on port 9000")
    mcp_app.run(debug=True, host='127.0.0.1', port=9000)
