import os
import re
import time
import logging
import base64
from flask import Flask, request, jsonify, render_template
import requests
from azure.storage.blob import BlobServiceClient
from weasyprint import HTML
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# -------------------- CONFIGURATION --------------------
API_URL        = ""
API_TOKEN      = os.environ.get("API_TOKEN")
BEARER_TOKEN   = os.environ.get("BEARER_TOKEN")
AZURE_CONN_STR = os.environ.get("AZURE_CONN_STR")
CONTAINER_NAME = os.environ.get("CONTAINER_NAME", "images")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fluxdev-flask")
app = Flask(__name__)
os.makedirs("static/generated_images", exist_ok=True)
GUID_REGEX = re.compile(
    r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', re.IGNORECASE
)

# -------------------- UTILS --------------------
def upload_blob(local_path, blob_name):
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONN_STR)
    try:
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        try:
            container_client.create_container()
        except Exception:
            pass  # Ignore if container exists

        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
        with open(local_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        return f"https://whiperimages.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}"
    except Exception as ex:
        logger.error(f"Azure Blob upload error: {ex}")
        return None


def handle_api_error(error, request_id):
    """
    Convert technical errors into user-friendly messages
    """
    if hasattr(error, "response") and error.response is not None:
        status_code = error.response.status_code

        if status_code == 401:
            logger.error(f"API Authentication failed for request {request_id}")
            return {
                "status": "error",
                "message": "API authentication failed. Please check your API configuration.",
                "user_message": "The image generator is not properly configured. Please contact the administrator.",
                "error_code": "AUTH_FAILED",
                "request_id": request_id,
            }
        elif status_code == 403:
            return {
                "status": "error",
                "message": "API access forbidden - insufficient permissions",
                "user_message": "You don't have permission to use this service.",
                "error_code": "ACCESS_FORBIDDEN",
                "request_id": request_id,
            }
        elif status_code == 429:
            return {
                "status": "error",
                "message": "API rate limit exceeded",
                "user_message": "Too many requests. Please try again in a few minutes.",
                "error_code": "RATE_LIMITED",
                "request_id": request_id,
            }
        elif status_code >= 500:
            return {
                "status": "error",
                "message": "External API service error",
                "user_message": "The image generation service is temporarily unavailable. Please try again later.",
                "error_code": "SERVICE_ERROR",
                "request_id": request_id,
            }

    logger.error(f"Unexpected error for request {request_id}: {str(error)}")
    return {
        "status": "error",
        "message": "An unexpected error occurred",
        "user_message": "Something went wrong. Please try again or contact support.",
        "error_code": "UNKNOWN_ERROR",
        "request_id": request_id,
    }


def check_api_configuration():
    """
    Check if required API keys are properly configured
    """
    missing_config = []

    if not API_TOKEN or API_TOKEN == "your_runpod_api_token_here":
        missing_config.append("API_TOKEN")
    if not BEARER_TOKEN or BEARER_TOKEN == "your_bearer_token_here":
        missing_config.append("BEARER_TOKEN")
    if not AZURE_CONN_STR or AZURE_CONN_STR == "your_azure_connection_string_here":
        missing_config.append("AZURE_CONN_STR")

    return missing_config


# -------------------- ROUTES --------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate_image():
    data = request.get_json(force=True)
    rid = data.get("request_id")
    prompt = data.get("prompt")
    width = data.get("width", 512)
    height = data.get("height", 512)

    if not all([rid, prompt]):
        return jsonify(status="error", message="Missing request_id or prompt"), 400
    if not GUID_REGEX.match(rid):
        return jsonify(status="error", message="request_id must be a valid GUID"), 400

    missing_config = check_api_configuration()
    if missing_config:
        logger.warning(f"Missing API configuration: {missing_config}")
        return (
            jsonify(
                status="error",
                message="Service configuration incomplete",
                user_message=f"The service is not properly configured. Missing: {', '.join(missing_config)}",
                error_code="CONFIG_MISSING",
                request_id=rid,
                missing_config=missing_config,
            ),
            503,
        )

    headers = {"Authorization": f"Bearer {BEARER_TOKEN}", "Content-Type": "application/json"}
    payload = {"input": {"prompt": prompt, "width": width, "height": height}}

    try:
        logger.info(f"Submitting job to RunPod /run for request {rid}")
        response = requests.post(f"{API_URL}/run", json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        job_info = response.json()
        job_id = job_info.get("id")
        if not job_id:
            raise ValueError("Job ID not found in /run response.")

        # Poll for status
        status_url = f"{API_URL}/status/{job_id}"
        t_start = time.time()
        while True:
            poll = requests.get(status_url, headers=headers, timeout=30)
            poll.raise_for_status()
            status_data = poll.json()
            if status_data.get("status") == "COMPLETED":
                result = status_data
                break
            elif status_data.get("status") in ("FAILED", "CANCELLED"):
                raise RuntimeError(f"Generation {status_data.get('status')}: {status_data.get('error', '')}")
            if time.time() - t_start > 120:
                raise TimeoutError("Timed out waiting for completed job.")
            time.sleep(2)

        # Parse output
        image_url = None
        output = result.get("output")
        if isinstance(output, dict):
            image_url = output.get("image_url") or output.get("image")
        elif isinstance(output, str):
            image_url = output
        elif isinstance(output, list) and output and isinstance(output[0], str):
            image_url = output[0]
        if not image_url:
            raise ValueError("image_url not found in output.")

        save_path = f"static/generated_images/{rid}.png"

        if image_url.startswith("data:image"):
            base64_data = image_url.split(",", 1)[-1]
            image_data = base64.b64decode(base64_data)
            with open(save_path, "wb") as f:
                f.write(image_data)
        elif image_url.startswith("http"):
            img_r = requests.get(image_url, stream=True, timeout=20)
            img_r.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in img_r.iter_content(1024):
                    f.write(chunk)
        else:
            raise ValueError("Unrecognized image_url format!")

        blob_url = upload_blob(save_path, f"{rid}.png")
        return jsonify(status="success", image_url=f"/generated_images/{rid}.png", blob_url=blob_url)

    except requests.exceptions.RequestException as e:
        error_response = handle_api_error(e, rid)
        return jsonify(error_response), 400
    except Exception as e:
        logger.exception(f"Image generation error for request {rid}")
        error_response = handle_api_error(e, rid)
        return jsonify(error_response), 500


@app.route("/convert_html_to_pdf", methods=["POST"])
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
        HTML(string=html_content, base_url=request.host_url).write_pdf(pdf_path)
        blob_url = upload_blob(pdf_path, pdf_filename)
        return jsonify(status="success", pdf_blob_url=blob_url)
    except Exception as e:
        logger.exception("PDF generation error")
        return jsonify(status="error", message=str(e)), 500


@app.route("/health", methods=["GET"])
def health_check():
    missing_config = check_api_configuration()
    health_status = {
        "service": "Image Generator",
        "status": "healthy" if not missing_config else "degraded",
        "timestamp": time.time(),
        "configuration": {
            "api_configured": len(missing_config) == 0,
            "missing_config": missing_config,
            "endpoints": {
                "generate": "/generate",
                "pdf_convert": "/convert_html_to_pdf",
                "health": "/health",
            },
        },
    }
    status_code = 200 if not missing_config else 503
    return jsonify(health_status), status_code


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8000)
