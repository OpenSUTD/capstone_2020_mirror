import glob
from bs4 import BeautifulSoup, Tag, Comment
import re
import logging
import os
import gc
from datetime import datetime

BUILD_TIME = datetime.now().strftime("%d %B %Y, %H:%M:%S")
logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "CRITICAL"))


# change index
for html_file_path in glob.glob("**/index.html", recursive=True):
    with open(html_file_path, "rb+") as file:
        soup = BeautifulSoup(file.read(), "lxml")
        soup.title.string = "SUTD Capstone"
        file.seek(0)
        file.write(bytes(str(soup), "utf-8"))
        file.truncate()
        soup.decompose()
        gc.collect()

for html_file_path in glob.glob("**/*.html", recursive=True):
    if "apos-minified" in html_file_path:
        continue
    try:
        with open(html_file_path, "rb+") as file:
            soup = BeautifulSoup(file.read(), "lxml")
            # is this even valid html
            if soup.head is None:
                continue

            try:
                # try to derive the page url
                ORIGINAL_URL = "https://capstone.sutd.edu.sg"
                for comments in soup.findAll(
                    text=lambda text: isinstance(text, Comment)
                ):
                    try:
                        comment = comments.extract().strip()
                        if comment.index("Mirrored from") == 0:
                            m = re.search(r"Mirrored from (.*) by HTTrack", comment)
                            ORIGINAL_URL = f"https://{m.group(1)}"
                            break
                    except:
                        break
            except Exception as ex:
                logger.error(f"Unable to derive page url for {html_file_path}")
            # add meta tags
            # is it project?
            try:
                if len(soup.select("div.project-detail_detail")) != 0:
                    # is project
                    project_name = soup.select(
                        "div.project-detail_detail .detail-title h2"
                    )[0].string
                    og_preview_name = project_name
                    og_preview_description = (
                        "[MIRROR] SUTD Capstone Project Virtual Showcase"
                    )
                else:
                    og_preview_name = "[MIRROR] SUTD Virtual Capstone Showcase 2020"
                    og_preview_description = (
                        "Find out more about SUTD's Capstone projects"
                    )
                meta_tag_attrs = [
                    {"property": "og:title", "content": og_preview_name},
                    {"property": "og:description", "content": og_preview_description},
                    {"name": "twitter:title", "content": og_preview_name},
                    {"name": "twitter:description", "content": og_preview_description},
                ]
                meta_tags = [soup.new_tag("meta", attrs=a) for a in meta_tag_attrs]
                for meta_tag in meta_tags:
                    soup.head.append(meta_tag)
            except Exception as ex:
                logger.error(f"Unable to add meta tags on file {html_file_path}")
            # add mirror build notice
            try:
                soup.select_one(".navbar-default").append(
                    BeautifulSoup(
                        f"""
        <div>You're viewing a mirror built at {BUILD_TIME}.
            <a href="{ORIGINAL_URL}">Click here</href> to go to the original version.
            <a href="https://github.com/OpenSUTD/capstone_2020_mirror">More Info</a>
        </div>""",
                        "html.parser",
                    )
                )
            except Exception as ex:
                logger.error(f"Unable to add mirror notice on file {html_file_path}")
            # attempt to restore data tags
            # try:
            #     remote_response = requests.get(ORIGINAL_URL, verify=False, stream=True)
            #     remote_response.raw.decode_content = True
            #     # tree = lxml.html.parse(remote_response.raw)
            #     remote_soup = BeautifulSoup(remote_response.raw, "lxml")
            #     tags_with_data = soup.find_all(
            #         re.compile(".*"), attrs={"data-apos-widget-id": re.compile(".*")}
            #     )
            #     for tag in tags_with_data:
            #         this_widget_id = tag["data-apos-widget-id"]
            #         matching_tag = remote_soup.find(
            #             re.compile(".*"),
            #             attrs={"data-apos-widget-id": tag["data-apos-widget-id"]},
            #         )
            #         if matching_tag is None:
            #             continue
            #         tag["data"] = matching_tag["data"]
            # except Exception as ex:
            #     logger.error(f"Unable to restore data stag for file {html_file_path}")
            # fix youtube video links
            try:
                to_replace = [
                    i
                    for i in soup.select("img.apos-video-thumbnail")
                    if "i.ytimg.com/vi/" in i["src"]
                ]
                video_id_matcher = re.compile(r"i\.ytimg\.com/vi/(\w+)/")
                for img in to_replace:
                    video_id = video_id_matcher.search(img["src"]).group(1)
                    iframe: Tag = soup.new_tag("iframe")
                    iframe["src"] = f"https://www.youtube.com/embed/{video_id}"
                    iframe["frameborder"] = "0"
                    iframe["style"] = "height: calc(100vw / 16 * 9)"
                    iframe[
                        "allow"
                    ] = "accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture"
                    iframe["allowfullscreen"] = ""
                    img.replace_with(iframe)
            except Exception as ex:
                logger.error(
                    f"Unable to convert youtube video thumbnail for {html_file_path}"
                )
            # save the file
            file.seek(0)
            file.write(bytes(str(soup), "utf-8"))
            file.truncate()
            soup.decompose()
            gc.collect()
    except:
        logger.error(f"Error ocurred for file {html_file_path}")
        pass
