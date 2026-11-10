from typing import TYPE_CHECKING, override

from bs4 import BeautifulSoup
from remanga.modules.core import ParserCore

from melon.core.base.formats.base_format.branch import Branch
from melon.core.base.formats.base_format.chapter import BaseChapter
from melon.core.base.formats.ranobe.chapter import Chapter
from melon.core.base.formats.ranobe.enums import ChapterType
from melon.core.base.parser.presets import BaseRanobeParser
from melon.core.html.allowed_tags import ALLOWED_TAGS

if TYPE_CHECKING:
	from bs4 import Tag
	from remanga.modules.slugger import Slugger
	from remanga.settings.custom import CustomSettingsModel  # noqa: F401

	from melon.core.base.structs.image import ImageData
	from melon.core.html.base_elements import BaseElement
	from melon.core.html.elements import Paragraph
	from melon.sdk.html_parser import HyperTextParser

	from . import SourceOperator  # noqa: F401

class Parser(BaseRanobeParser["SourceOperator", "CustomSettingsModel"]):
	"""Parser."""

	@property
	def core(self) -> ParserCore:
		"""Content type independent parser core."""

		return self.__core

	@property
	def html_parser(self) -> "HyperTextParser":
		"""HTML elements parser."""

		return self.__core.html_parser

	@property
	def is_paid_chapters_locked(self) -> bool:
		"""Condition: is paid chapter locked."""

		return self.__is_paid_chapters_locked

	@property
	def slugger(self) -> "Slugger":
		"""Title slug updater."""

		return self.__core.slugger

	@override
	def _amend(self, branch: Branch, chapter: BaseChapter) -> str | None:
		"""
		Amend chapter content.

		Args:
			branch (Branch): Branch.
			chapter (Any): Chapter

		Returns:
			str | None: Optional additional message about amending result.
		"""

		if not isinstance(chapter, Chapter):
			raise TypeError("Incorrect chapter type given to amending.")

		elements = self.__get_chapter_elements(chapter)
		chapter.set_elements(elements)

	@override
	def _parse(self):
		"""Parse title data witchout chapters content."""

		data: dict = self.core.parse_main_data()

		self.__get_original_content_language(data)

	@override
	def _post_init(self):
		"""Execute after instance initialization."""

		self.__is_paid_chapters_locked: bool = False
		self.__core: ParserCore = ParserCore(self, Chapter)

	def __get_chapter_type(self, header: str) -> ChapterType | None:
		"""
		Get chapter type.

		Args:
			header (str): Chapter header.

		Returns:
			ChapterType | None: Chapter type or `None` if unable determine.
		"""

		if not header:
			return

		header = header.lower()

		#---> afterword
		#==========================================================================================#
		if "послесловие" in header:
			return ChapterType.Afterword

		#---> art
		#==========================================================================================#
		if header.startswith("начальные") and "иллюстрации" in header:
			return ChapterType.Art

		#---> epilogue
		#==========================================================================================#
		if "эпилог" in header:
			return ChapterType.Epilogue

		#---> extra
		#==========================================================================================#
		if any((
			header.startswith("дополнительн") and "истори" in header,
			header.startswith("бонус") and "истори",
			header.startswith("экстра"),
		)):
			return ChapterType.Extra

		#---> glossary
		#==========================================================================================#
		if header.startswith("глоссарий"):
			return ChapterType.Glossary

		#---> prologue
		#==========================================================================================#
		if "пролог" in header:
			return ChapterType.Prologue

		#---> trash
		#==========================================================================================#
		if header.startswith("реквизиты") and "переводчик" in header: return ChapterType.Trash
		if header.startswith("примечани") and "переводчик" in header: return ChapterType.Trash

		#---> chapter
		#==========================================================================================#
		# if "глава" in name: return ChaptersTypes.chapter

		return None

	def __get_chapter_elements(self, chapter: Chapter) -> tuple["BaseElement | ImageData", ...]:
		"""
		Get chapter elements.

		Returns:
			tuple[BaseElement, ...]: Chapter elements.
		"""

		elements: list[BaseElement | ImageData] = []

		if chapter.is_paid and self.is_paid_chapters_locked:
			self.portals.chapter_skipped(chapter)
			return ()

		response = self.requestor.get(f"https://{self.manifest.domain}/api/v2/titles/chapters/{chapter.id}/")
		data: dict | None = response.json

		if not response.ok or not data:
			self.portals.request_error(response, "Unable to request chapter content.")

		if "content" not in data:

			if chapter.is_paid:
				self._is_paid_chapters_locked = True

			self.portals.chapter_skipped(chapter)
			return ()

		content: str = data["content"]
		soup = BeautifulSoup(content, "html.parser")

		for section in soup.find_all(ALLOWED_TAGS.names + ("table",)):

			match section.name:

				case "h1" | "h2" | "h3" | "h4" | "h5" | "h6":
					header = self.html_parser.parse_header(section)
					if header: elements.append(header)

				case "p" | "pre":
					elements.extend(self.html_parser.parse_paragraphs(section, allow_footnotes = False))

				case "img":
					image = self.html_parser.parse_image(section)
					if image: elements.append(image)

				case "blockquote":
					blockquote = self.html_parser.parse_blockquote(section, paragraphs_tags = ("p", "pre"))
					if blockquote: elements.append(blockquote)

				case "table":
					elements.extend(self.__parse_table(section))

		return tuple(elements)

	def __get_original_content_language(self, data: dict):
		"""
		Get title original content language.

		Args:
			data (dict): Title data.
		"""

		type_data: dict | None = data.get("type")

		if not type_data:
			return

		value: str | None = type_data.get("name")

		if not value:
			return

		determinations: dict[str, str | None] = {
			"Другое": None,
			"Авторское": "rus",
			"Япония": "jpn",
			"Корея": "kor",
			"Китай": "zho",
			"Запад": "eng",
			"Фанфики": None,
		}

		if value in determinations:
			self.title.data.set_original_language(determinations[value])

	def __parse_table(self, tag: "Tag") -> tuple["Paragraph", ...]:

		if tag.name != "table":
			raise ValueError("Table can be parsed only from same tag.")

		tbody: Tag | None = tag.find("tbody")

		if not tbody:
			return ()

		paragraphs: list[Paragraph] = []

		for row in tbody.find_all("tr", recursive = False):
			text: str = row.get_text().strip()

			if not text:
				continue

			new_tag: Tag = self.html_parser.make_tag("p", text)
			new_paragraphs: tuple[Paragraph, ...] = self.html_parser.parse_paragraphs(new_tag, allow_footnotes = False)
			paragraphs.extend(new_paragraphs)

		return tuple(paragraphs)
