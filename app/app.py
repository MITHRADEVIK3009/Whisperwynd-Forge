import os
import re
import time
import json
import base64
import logging
import requests
from datetime import datetime
from functools import wraps
from collections import defaultdict, deque

from flask import Flask, request, jsonify, render_template
from azure.storage.blob import BlobServiceClient
from weasyprint import HTML
from dotenv import load_dotenv

# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------
load_dotenv()

app = Flask(__name__)

API_URL        = ""
API_TOKEN      = os.environ.get("API_TOKEN")
BEARER_TOKEN   = os.environ.get("BEARER_TOKEN")
AZURE_CONN_STR = os.environ.get("AZURE_CONN_STR")
CONTAINER_NAME = os.environ.get("CONTAINER_NAME", "images")

os.makedirs("static/generated_images", exist_ok=True)

GUID_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# -------------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler(),
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
    missing = []
    if not os.getenv("AZURE_STORAGE_KEY"):
        missing.append("AZURE_STORAGE_KEY")
    return missing

def validate_request_data(data):
    """Validate incoming request data"""
    rid = data.get("request_id")
    if not rid:
        return False, "Missing request_id"
    if not GUID_REGEX.match(rid):
        return False, "request_id must be a valid GUID"
    return True, "Valid"

def process_image_request(data):
    """Core image processing logic"""
    rid = data.get("request_id")
    prompt = data.get("prompt")
    width = data.get("width", 512)
    height = data.get("height", 512)
    
    if not prompt:
        return {"status": "error", "message": "Missing prompt"}
    
    # Simulate processing (replace with actual RunPod call)
    logger.info(f"Processing image request: {rid} - '{prompt}' at {width}x{height}")
    return {
        "status": "success", 
        "message": "Image generation completed",
        "request_id": rid,
        "prompt": prompt,
        "dimensions": f"{width}x{height}"
    }

def process_pdf_request(data):
    """Core PDF processing logic"""
    rid = data.get("request_id")
    html_content = data.get("html")
    
    if not html_content:
        return {"status": "error", "message": "Missing html content"}
    
    try:
        pdf_filename = f"{rid}.pdf"
        pdf_path = os.path.join("static/generated_images", pdf_filename)
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        
        HTML(string=html_content, base_url="http://localhost:8000/").write_pdf(pdf_path)
        blob_url = upload_blob(pdf_path, pdf_filename)
        
        return {
            "status": "success",
            "message": "PDF generated successfully",
            "pdf_blob_url": blob_url,
            "request_id": rid
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_metrics():
    """Get current application metrics"""
    return app_metrics.get_stats()

def upload_blob(local_path, blob_name):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONN_STR)
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        try:
            container_client.create_container()
        except Exception:
            pass
        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
        with open(local_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        return f"https://whiperimages.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}"
    except Exception as ex:
        logger.error(f"Azure Blob upload error: {ex}")
        return None

# -------------------------------------------------------------------
# ROUTES
# -------------------------------------------------------------------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
@monitor_performance
@log_request_details
def generate_image():
    data = request.get_json(force=True)
    rid = data.get("request_id")
    prompt = data.get("prompt")
    width = data.get("width", 512)
    height = data.get("height", 512)

    logger.info(f"IMAGE GENERATION REQUEST: ID={rid}, Prompt='{prompt[:100]}', Dimensions={width}x{height}")

    # Validation
    if not all([rid, prompt]):
        app_metrics.record_error("VALIDATION_ERROR", "Missing required fields")
        return jsonify(status="error", message="Missing request_id or prompt"), 400
    if not GUID_REGEX.match(rid):
        app_metrics.record_error("VALIDATION_ERROR", "Invalid GUID format")
        return jsonify(status="error", message="request_id must be a valid GUID"), 400

    missing_config = check_api_configuration()
    if missing_config:
        return jsonify(status="error", message="Service configuration incomplete"), 503

    headers = {"Authorization": f"Bearer {BEARER_TOKEN}", "Content-Type": "application/json"}
    payload = {"input": {"prompt": prompt, "width": width, "height": height}}

    # --- Stub (replace with actual RunPod call) ---
    logger.info(f"Would generate image with prompt: '{prompt}' at {width}x{height}")
    return jsonify(status="info", message="Stub - replace with RunPod call", request_id=rid)

@app.route("/convert_html_to_pdf", methods=["POST"])
@monitor_performance
def convert_html_to_pdf():
    data = request.get_json(force=True)
    rid = data.get("request_id")
    html_content = data.get("html")

    if not rid or not html_content:
        return jsonify(status="error", message="Missing request_id or html"), 400
    if not GUID_REGEX.match(rid):
        return jsonify(status="error", message="request_id must be a valid GUID"), 400

    try:
        pdf_filename = f"{rid}.pdf"
        pdf_path = os.path.join("static/generated_images", pdf_filename)
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

        HTML(string=html_content, base_url=request.host_url).write_pdf(pdf_path)
        blob_url = upload_blob(pdf_path, pdf_filename)
        return jsonify(status="success", pdf_blob_url=blob_url)
    except Exception as e:
        logger.exception("PDF generation error")
        return jsonify(status="error", message=str(e)), 500

@app.route("/stats", methods=["GET"])
def get_stats():
    stats = app_metrics.get_stats()
    stats["status"] = "healthy" if app_metrics.failed_generations < app_metrics.successful_generations else "degraded"
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
    }
    return jsonify(health_status), (200 if not missing_config else 503)

# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting Image Generator Application")
    app.run(debug=True, host='127.0.0.1', port=8000)
