import os
import re
import time
import json
import logging
from datetime import datetime
from functools import wraps
from collections import defaultdict, deque
from flask import Flask, request, jsonify
from weasyprint import HTML

# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------

app = Flask(__name__)

# GUID format regex
GUID_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Configure enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),  # Log to file
        logging.StreamHandler(),         # Log to console
    ],
)
logger = logging.getLogger("image_generator")


# -------------------------------------------------------------------
# PERFORMANCE METRICS
# -------------------------------------------------------------------

class AppMetrics:
    def __init__(self):
        self.request_count = 0
        self.total_requests = defaultdict(int)
        self.response_times = deque(maxlen=100)
        self.error_count = defaultdict(int)
        self.start_time = time.time()
        self.successful_generations = 0
        self.failed_generations = 0

    def record_request(self, endpoint, method):
        self.request_count += 1
        self.total_requests[f"{method} {endpoint}"] += 1
        logger.info(f"Request #{self.request_count} - {method} {endpoint}")

    def record_response_time(self, duration, success=True):
        self.response_times.append(duration)
        if success:
            self.successful_generations += 1
        else:
            self.failed_generations += 1

    def record_error(self, error_type, error_message):
        self.error_count[error_type] += 1
        logger.error(f"Error recorded: {error_type} - {error_message}")

    def get_stats(self):
        uptime = time.time() - self.start_time
        avg_response_time = (
            sum(self.response_times) / len(self.response_times)
            if self.response_times else 0
        )

        return {
            "uptime_seconds": round(uptime, 2),
            "uptime_formatted": f"{uptime//3600:.0f}h {(uptime%3600)//60:.0f}m {uptime%60:.0f}s",
            "total_requests": self.request_count,
            "successful_generations": self.successful_generations,
            "failed_generations": self.failed_generations,
            "success_rate": (
                f"{(self.successful_generations / (self.successful_generations + self.failed_generations) * 100):.1f}%"
                if (self.successful_generations + self.failed_generations) > 0 else "N/A"
            ),
            "average_response_time": f"{avg_response_time:.2f}s",
            "recent_response_times": list(self.response_times)[-10:],
            "error_breakdown": dict(self.error_count),
            "endpoint_usage": dict(self.total_requests),
        }


app_metrics = AppMetrics()


# -------------------------------------------------------------------
# DECORATORS
# -------------------------------------------------------------------

def monitor_performance(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        request_id = "unknown"
        endpoint = func.__name__

        if hasattr(request, "get_json"):
            try:
                data = request.get_json(force=True) if request.is_json else {}
                request_id = data.get("request_id", "unknown")
            except Exception:
                pass

        app_metrics.record_request(endpoint, getattr(request, "method", "UNKNOWN"))
        logger.info(f"STARTING {func.__name__} - Request ID: {request_id}")

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            app_metrics.record_response_time(duration, success=True)
            logger.info(f"SUCCESS {func.__name__} - Duration: {duration:.2f}s - Request ID: {request_id}")
            return result
        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__
            app_metrics.record_response_time(duration, success=False)
            app_metrics.record_error(error_type, str(e))
            logger.error(
                f"FAILED {func.__name__} - Duration: {duration:.2f}s - Error: {error_type}: {str(e)} - Request ID: {request_id}"
            )
            raise
    return wrapper


def log_request_details(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if request.is_json:
            data = request.get_json(force=True)
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "endpoint": request.endpoint,
                "method": request.method,
                "request_id": data.get("request_id", "unknown"),
                "prompt_length": len(data.get("prompt", "")),
                "prompt_preview": (
                    data.get("prompt", "")[:50] + "..."
                    if len(data.get("prompt", "")) > 50
                    else data.get("prompt", "")
                ),
                "dimensions": f"{data.get('width', 'unknown')}x{data.get('height', 'unknown')}",
                "user_agent": request.headers.get("User-Agent", "unknown")[:100],
                "ip_address": request.remote_addr,
            }
            logger.info(f"REQUEST DETAILS: {json.dumps(log_data, indent=2)}")
        return func(*args, **kwargs)
    return wrapper


# -------------------------------------------------------------------
# UTILS
# -------------------------------------------------------------------

def check_api_configuration():
    """Dummy placeholder until real API config is added"""
    missing = []
    if not os.getenv("AZURE_STORAGE_KEY"):
        missing.append("AZURE_STORAGE_KEY")
    return missing

def upload_blob(local_path, blob_name):
    """Stub for blob upload - replace with actual Azure SDK upload"""
    return f"http://localhost:5000/static/generated_images/{blob_name}"


# -------------------------------------------------------------------
# ROUTES
# -------------------------------------------------------------------

@app.route("/generate", methods=["POST"])
@monitor_performance
@log_request_details
def generate_image():
    data = request.get_json(force=True)
    rid = data.get("request_id")
    prompt = data.get("prompt")
    width = data.get("width", 512)
    height = data.get("height", 512)

    logger.info(f"IMAGE GENERATION REQUEST: ID={rid}, Prompt='{prompt[:100]}', Dimensions={width}x{height}")

    if not all([rid, prompt]):
        app_metrics.record_error("VALIDATION_ERROR", "Missing required fields")
        return jsonify(status="error", message="Missing request_id or prompt"), 400

    if not GUID_REGEX.match(rid):
        app_metrics.record_error("VALIDATION_ERROR", "Invalid GUID format")
        return jsonify(status="error", message="request_id must be a valid GUID"), 400

    missing_config = check_api_configuration()
    if missing_config:
        app_metrics.record_error("CONFIG_ERROR", f"Missing config: {', '.join(missing_config)}")
        return jsonify(
            status="error",
            message="Service configuration incomplete",
            user_message=f"Missing: {', '.join(missing_config)}",
            error_code="CONFIG_MISSING",
            request_id=rid,
            missing_config=missing_config,
        ), 503

    logger.info(f"Would generate image with prompt: '{prompt}' at {width}x{height}")
    return jsonify(
        status="info",
        message="Image generation would proceed here (API keys needed)",
        request_id=rid,
        prompt=prompt,
        dimensions=f"{width}x{height}",
    )


@app.route("/convert_html_to_pdf", methods=["POST"])
@monitor_performance
def convert_html_to_pdf():
    data = request.get_json(force=True)
    rid = data.get("request_id")
    html_content = data.get("html")

    if not rid or not html_content:
        app_metrics.record_error("VALIDATION_ERROR", "Missing PDF conversion fields")
        return jsonify(status="error", message="Missing request_id or html"), 400

    if not GUID_REGEX.match(rid):
        app_metrics.record_error("VALIDATION_ERROR", "Invalid GUID for PDF")
        return jsonify(status="error", message="request_id must be a valid GUID"), 400

    try:
        pdf_filename = f"{rid}.pdf"
        pdf_path = os.path.join("static/generated_images", pdf_filename)
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

        HTML(string=html_content, base_url=request.host_url).write_pdf(pdf_path)
        blob_url = upload_blob(pdf_path, pdf_filename)

        logger.info(f"PDF CREATED - {pdf_filename}, Blob URL: {blob_url}")
        return jsonify(status="success", pdf_blob_url=blob_url)
    except Exception as e:
        logger.exception(f"PDF CONVERSION FAILED - ID: {rid}")
        app_metrics.record_error("PDF_ERROR", str(e))
        return jsonify(status="error", message=str(e)), 500


@app.route("/stats", methods=["GET"])
def get_stats():
    stats = app_metrics.get_stats()
    stats["status"] = "healthy" if app_metrics.failed_generations < app_metrics.successful_generations else "degraded"
    stats["most_common_errors"] = dict(
        sorted(app_metrics.error_count.items(), key=lambda x: x[1], reverse=True)[:5]
    )
    logger.info(f"STATS REQUESTED: {json.dumps(stats, indent=2)}")
    return jsonify(stats)


@app.route("/health", methods=["GET"])
def health_check():
    missing_config = check_api_configuration()
    stats = app_metrics.get_stats()
    health_status = {
        "service": "Image Generator",
        "status": "healthy" if not missing_config else "degraded",
        "timestamp": datetime.now().isoformat(),
        "uptime": stats["uptime_formatted"],
        "configuration": {
            "api_configured": len(missing_config) == 0,
            "missing_config": missing_config,
        },
        "performance": {
            "total_requests": stats["total_requests"],
            "success_rate": stats["success_rate"],
            "average_response_time": stats["average_response_time"],
        },
        "endpoints": {
            "generate": "/generate",
            "pdf_convert": "/convert_html_to_pdf",
            "health": "/health",
            "stats": "/stats",
        },
    }
    return jsonify(health_status), (200 if not missing_config else 503)


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting Image Generator Application")
    logger.info("Statistics available at: http://localhost:5000/stats")
    logger.info("Health check available at: http://localhost:5000/health")
    app.run(debug=True)
