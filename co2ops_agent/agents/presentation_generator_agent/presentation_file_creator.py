try:
    from pptx import Presentation
    from pptx.util import Pt
    from pptx.dml.color import RGBColor
except ImportError:
    Presentation = None
    Pt = None
    RGBColor = None

try:
    from lxml import etree
except ImportError:
    etree = None

from io import BytesIO
import requests
import logging
import json
import os
from co2ops_agent.secrets_access_manager import access_secret

logger = logging.getLogger(__name__)

def get_shape_by_name(slide, target_name):
    for shape in slide.shapes:
        if shape.name == target_name:
            return shape
    return None

def set_text_with_optional_style(shape, text, font_size=None, font_color=None, bold=None):
    if not shape.has_text_frame:
        return

    text_frame = shape.text_frame
    text_frame.clear()  # Optional: clear existing text if you want full control

    for i, line in enumerate(text.split("\n")):
        p = text_frame.add_paragraph() if i > 0 else text_frame.paragraphs[0]
        run = p.add_run()

        line = line.strip()

        if line.startswith("-"):
            run.text = line[1:].strip()
        else:
            run.text = line
            p._pPr.insert(0, etree.Element("{http://schemas.openxmlformats.org/drawingml/2006/main}buNone"))

        if text=="THANK YOU!":
            p._pPr.insert(0, etree.Element("{http://schemas.openxmlformats.org/drawingml/2006/main}buNone"))

        font = run.font
        if font_size:
            font.size = font_size
        if font_color:
            font.color.rgb = font_color
        if bold is not None:
            font.bold = bold

def create_presentation(content: dict, tool_context=None, state=None):
    """
    Input: Dict containing the data for slides
    """
    chart_image_map = {}
    if state is not None:
        if hasattr(state, "custom_metadata") and "chart_links" in state.custom_metadata:
            chart_image_map = state.custom_metadata["chart_links"]
        elif hasattr(state, "get") and state.get("chart_links"):
            chart_image_map = state.get("chart_links")
        elif isinstance(state, dict) and "chart_links" in state:
            chart_image_map = state["chart_links"]
    elif tool_context is not None and hasattr(tool_context, "state") and isinstance(tool_context.state, dict) and "chart_links" in tool_context.state:
        chart_image_map = tool_context.state["chart_links"]

    if chart_image_map:
        if "forecast_overview" in content and "[[chart_carbon_timeseries]]" in chart_image_map:
            content["forecast_overview"]["chart_image_uri"] = chart_image_map["[[chart_carbon_timeseries]]"]
        if "regional_utilization" in content and "[[chart_underutilization]]" in chart_image_map:
            content["regional_utilization"]["chart_image_uri"] = chart_image_map["[[chart_underutilization]]"]
        if "top_recommendations" in content and "[[chart_region_utilization]]" in chart_image_map:
            content["top_recommendations"]["chart_image_uri"] = chart_image_map["[[chart_region_utilization]]"]
        if "instance_behavior_insights" in content and "[[chart_cpu_vs_carbon]]" in chart_image_map:
            content["instance_behavior_insights"]["chart_image_uri"] = chart_image_map["[[chart_cpu_vs_carbon]]"]

    # Load base presentation template
    template_candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "custom_template.pptx"),
        os.path.join(os.getcwd(), "co2ops_agent", "custom_template.pptx"),
        os.path.join(os.getcwd(), "custom_template.pptx")
    ]
    template_path = None
    for cand in template_candidates:
        if os.path.exists(cand):
            template_path = cand
            break

    if template_path:
        prs = Presentation(template_path)
    else:
        try:
            response_template = requests.get("https://storage.googleapis.com/presentation-templates/custom_template.pptx", timeout=5)
            prs = Presentation(BytesIO(response_template.content))
        except Exception:
            prs = Presentation()

    if len(prs.slides) > 0:
        prs.slides._sldIdLst.remove(list(prs.slides._sldIdLst)[0])

    def load_image_bytes(uri_or_path: str) -> BytesIO:
        if not uri_or_path:
            return None
        clean_path = uri_or_path.replace("file:///", "").replace("file://", "")
        if os.path.exists(clean_path):
            with open(clean_path, "rb") as f:
                return BytesIO(f.read())
        elif uri_or_path.startswith("http"):
            try:
                res = requests.get(uri_or_path, timeout=5)
                if res.status_code == 200:
                    return BytesIO(res.content)
            except Exception:
                pass
        return None

    # HERO PAGE
    slide1 = prs.slides.add_slide(prs.slide_layouts[0])
    set_text_with_optional_style(get_shape_by_name(slide1, "Title 1"), "CO2Ops AWS Sustainability Report", font_size=Pt(44))
    set_text_with_optional_style(get_shape_by_name(slide1, "Subtitle 2"), content["hero_page"]["week_date_range"], font_size=Pt(20))

    # EXECUTIVE SUMMARY
    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    set_text_with_optional_style(get_shape_by_name(slide2, "Title 1"), "Executive Summary", font_size=Pt(30))
    set_text_with_optional_style(get_shape_by_name(slide2, "Text Placeholder 2"), content["executive_summary"]["content"], font_size=Pt(24))

    # FORECAST OVERVIEW
    slide3 = prs.slides.add_slide(prs.slide_layouts[2])
    set_text_with_optional_style(get_shape_by_name(slide3, "Title 1"), "Forecast Overview", font_size=Pt(30))
    image_shape = get_shape_by_name(slide3, "Picture Placeholder 2")
    img_bytes = load_image_bytes(content.get("forecast_overview", {}).get("chart_image_uri", ""))
    if image_shape and img_bytes:
        image_shape.insert_picture(img_bytes)
    set_text_with_optional_style(get_shape_by_name(slide3, "Text Placeholder 3"), content["forecast_overview"]["content"])

    # Regional Utilization
    slide4 = prs.slides.add_slide(prs.slide_layouts[3])
    set_text_with_optional_style(get_shape_by_name(slide4, "Title 1"), "Regional Utilization", font_size=Pt(30))
    image_shape = get_shape_by_name(slide4, "Picture Placeholder 2")
    img_bytes = load_image_bytes(content.get("regional_utilization", {}).get("chart_image_uri", ""))
    if image_shape and img_bytes:
        image_shape.insert_picture(img_bytes)
    set_text_with_optional_style(get_shape_by_name(slide4, "Text Placeholder 3"), content["regional_utilization"]["content"])

    # Top Recommendations
    slide5 = prs.slides.add_slide(prs.slide_layouts[4])
    set_text_with_optional_style(get_shape_by_name(slide5, "Title 1"), "Top AWS Recommendations", font_size=Pt(30))
    image_shape = get_shape_by_name(slide5, "Picture Placeholder 2")
    img_bytes = load_image_bytes(content.get("top_recommendations", {}).get("chart_image_uri", ""))
    if image_shape and img_bytes:
        image_shape.insert_picture(img_bytes)
    set_text_with_optional_style(get_shape_by_name(slide5, "Text Placeholder 3"), content["top_recommendations"]["content"], font_size=Pt(18))

    # Instance Behavior Insights
    slide6 = prs.slides.add_slide(prs.slide_layouts[5])
    set_text_with_optional_style(get_shape_by_name(slide6, "Title 1"), "Instance Behaviour Insights", font_size=Pt(30))
    image_shape = get_shape_by_name(slide6, "Picture Placeholder 2")
    img_bytes = load_image_bytes(content.get("instance_behavior_insights", {}).get("chart_image_uri", ""))
    if image_shape and img_bytes:
        image_shape.insert_picture(img_bytes)
    set_text_with_optional_style(get_shape_by_name(slide6, "Text Placeholder 3"), content["instance_behavior_insights"]["content"], font_size=Pt(18))

    # Thank you!
    slide7 = prs.slides.add_slide(prs.slide_layouts[6])
    set_text_with_optional_style(get_shape_by_name(slide7, "Text Placeholder 1"), "THANK YOU!", font_size=Pt(60))

    os.makedirs("presentations", exist_ok=True)
    raw_range = content.get("hero_page", {}).get("week_date_range", "Weekly")
    safe_range = raw_range.replace(" ", "_").replace("–", "-").replace(":", "-")
    filename = f"CO2Ops_AWS_Sustainability_{safe_range}.pptx"
    file_path = f"presentations/{filename}"
    prs.save(file_path)

    download_url = upload_pptx_to_s3_or_local(file_path, filename)

    return {
        "Download_link": download_url
    }


def upload_pptx_to_s3_or_local(filepath: str, filename: str) -> str:
    """Uploads PPTX presentation to Amazon S3 or returns local file URL."""
    bucket = os.getenv("AWS_REPORTS_BUCKET", "")

    if bucket:
        try:
            import boto3
            region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
            s3 = boto3.client("s3", region_name=region)
            s3.upload_file(
                filepath,
                bucket,
                f"presentations/{filename}",
                ExtraArgs={"ContentType": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
            )
            return s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": f"presentations/{filename}"},
                ExpiresIn=604800
            )
        except Exception as e:
            logger.debug(f"S3 presentation upload fallback: {e}")

    abs_path = os.path.abspath(filepath).replace('\\', '/')
    return f"file:///{abs_path}"

