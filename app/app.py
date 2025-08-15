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
API_URL      = "https://api.runpod.ai/v2/yjkyakuvnz1esw"
API_TOKEN    = os.environ.get("API_TOKEN")
BEARER_TOKEN = os.environ.get("BEARER_TOKEN")
AZURE_CONN_STR = os.environ.get("AZURE_CONN_STR")
CONTAINER_NAME = os.environ.get("CONTAINER_NAME", "images")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fluxdev-flask")
app = Flask(__name__)
os.makedirs("static/generated_images", exist_ok=True)
GUID_REGEX = re.compile(
    r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', re.IGNORECASE
)

def upload_blob(local_path, blob_name):
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONN_STR)
    try:
        # Ensure container exists
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        try:
            container_client.create_container()
        except Exception:
            pass  # Ignore if already exists

        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
        with open(local_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        return f"https://whiperimages.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}"
    except Exception as ex:
        logger.error(f"Azure Blob upload error: {ex}")
        return None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_image():
    data   = request.get_json(force=True)
    rid    = data.get("request_id")
    prompt = data.get("prompt")
    width  = data.get("width", 512)
    height = data.get("height", 512)

    # Basic validation
    if not all([rid, prompt]):
        return jsonify(status="error", message="Missing request_id or prompt"), 400
    if not GUID_REGEX.match(rid):
        return jsonify(status="error", message="request_id must be a valid GUID"), 400

    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "input": {
            "prompt": prompt,
            "width": width,
            "height": height
        }
    }

    try:
        logger.info("Submitting job to RunPod /run")
        # STEP 1: Start job
        response = requests.post(f"{API_URL}/run", json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        job_info = response.json()
        job_id = job_info.get("id")
        if not job_id:
            raise ValueError("Job ID not found in /run response.")

        # STEP 2: Poll for status
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
                logger.error(f"Full RunPod failure info: {status_data}")
                raise RuntimeError(f"Generation {status_data.get('status', 'FAILED')}: {status_data.get('error', '')}")
            # Timeout after 120 seconds
            if time.time() - t_start > 120:
                raise TimeoutError("Timed out waiting for completed job.")
            time.sleep(2)  # Poll interval

        # STEP 3: Parse output (robust for variants)
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

        # STEP 4: Save base64 or HTTP(S) image automatically
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

        # STEP 5: Upload to Azure Blob and return both URLs
        blob_url = upload_blob(save_path, f"{rid}.png")
        return jsonify(
            status="success",
            image_url=f"/generated_images/{rid}.png",
            blob_url=blob_url
        )

    except Exception as e:
        logger.exception("Image generation error")
        return jsonify(status="error", message=str(e)), 500

@app.route('/convert_html_to_pdf', methods=['POST'])
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
        # Convert the HTML string to PDF (WeasyPrint resolves external image links)
        HTML(string=html_content, base_url=request.host_url).write_pdf(pdf_path)
        # Upload to Azure Blob
        blob_url = upload_blob(pdf_path, pdf_filename)
        return jsonify(status="success", pdf_blob_url=blob_url)
    except Exception as e:
        logger.exception("PDF generation error")
        return jsonify(status="error", message=str(e)), 500

if __name__ == '__main__':
    app.run(debug=True)


