import requests
import uuid

html = """
<html>
  <body>
    <h1>Hello PDF</h1>
    <img src="https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png">
    <p>This is a demo of HTML to PDF with image.</p>
  </body>
</html>
"""

rid = str(uuid.uuid4())
resp = requests.post(
    "http://127.0.0.1:5000/convert_html_to_pdf",
    json={"request_id": rid, "html": html}
)
print(resp.json())

