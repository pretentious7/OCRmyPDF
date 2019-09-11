# © 2018 James R. Barlow: github.com/jbarlow83
#
# This file is part of OCRmyPDF.
#
# OCRmyPDF is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OCRmyPDF is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OCRmyPDF.  If not, see <http://www.gnu.org/licenses/>.

import logging
import re
import xml.etree.ElementTree as ET

from ..exec import ghostscript

gslog = logging.getLogger()

# Forgive me for I have sinned
# I am using regular expressions to parse XML. However the XML in this case,
# generated by Ghostscript, is self-consistent enough to be parseable.
regex_remove_char_tags = re.compile(
    br"""
    <char\b
    (?:   [^>]   # anything single character but >
        | \">\"  # special case: trap ">"
    )*
    />           # terminate with '/>'
""",
    re.VERBOSE,
)


def page_get_textblocks(infile, pageno, xmltext, height):
    """Get text boxes out of Ghostscript txtwrite xml"""

    root = xmltext
    if not hasattr(xmltext, 'findall'):
        return []

    def blocks():
        for span in root.findall('.//span'):
            bbox_str = span.attrib['bbox']
            font_size = span.attrib['size']
            pts = [int(pt) for pt in bbox_str.split()]
            pts[1] = pts[1] - int(float(font_size) + 0.5)
            bbox_topdown = tuple(pts)
            bb = bbox_topdown
            bbox_bottomup = (bb[0], height - bb[3], bb[2], height - bb[1])
            yield bbox_bottomup

    def joined_blocks():
        prev = None
        for bbox in blocks():
            if prev is None:
                prev = bbox
            if bbox[1] == prev[1] and bbox[3] == prev[3]:
                gap = prev[2] - bbox[0]
                height = abs(bbox[3] - bbox[1])
                if gap < height:
                    # Join boxes
                    prev = (prev[0], prev[1], bbox[2], bbox[3])
                    continue
            # yield previously joined bboxes and start anew
            yield prev
            prev = bbox
        if prev is not None:
            yield prev

    return [block for block in joined_blocks()]


def extract_text_xml(infile, pdf, pageno=None, log=gslog):
    existing_text = ghostscript.extract_text(infile, pageno=None)
    existing_text = regex_remove_char_tags.sub(b' ', existing_text)

    try:
        root = ET.fromstringlist([b'<document>\n', existing_text, b'</document>\n'])
        page_xml = root.findall('page')
    except ET.ParseError as e:
        log.error(
            "An error occurred while attempting to retrieve existing text in "
            "the input file. Will attempt to continue assuming that there is "
            "no existing text in the file. The error was:"
        )
        log.error(e)
        page_xml = [None] * len(pdf.pages)

    page_count_difference = len(pdf.pages) - len(page_xml)
    if page_count_difference != 0:
        log.error("The number of pages in the input file is inconsistent.")
        if page_count_difference > 0:
            page_xml.extend([None] * page_count_difference)
    return page_xml