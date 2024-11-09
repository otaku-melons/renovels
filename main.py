from Parsers.remanga.main import Parser as Progenitor

import Parsers.remanga.main as main 

from Source.Core.Formats.Ranobe import Branch, Chapter, ChaptersTypes, Ranobe, Statuses
from Source.Core.SystemObjects import SystemObjects

from dublib.Polyglot import HTML
from bs4 import BeautifulSoup

#==========================================================================================#
# >>>>> ОПРЕДЕЛЕНИЯ <<<<< #
#==========================================================================================#

VERSION = "1.0.0"
NAME = "renovels"
SITE = "renovels.org"
TYPE = Ranobe

main.NAME = NAME
main.SITE = SITE

#==========================================================================================#
# >>>>> ОСНОВНОЙ КЛАСС <<<<< #
#==========================================================================================#

class Parser(Progenitor):
	"""Парсер."""

	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#

	def __CheckChapterType(self, name: str) -> ChaptersTypes | None:
		"""
		Определяет при возможности тип главы.
			name – название главы.
		"""

		if not name: return None
		name = name.lower()

		#---> afterword
		#==========================================================================================#
		if "послесловие" in name: return ChaptersTypes.afterword

		#---> art
		#==========================================================================================#
		if name.startswith("начальные") and "иллюстрации" in name: return ChaptersTypes.art

		#---> epilogue
		#==========================================================================================#
		if "эпилог" in name: return ChaptersTypes.epilogue

		#---> extra
		#==========================================================================================#
		if name.startswith("дополнительн") and "истори" in name: return ChaptersTypes.extra
		if name.startswith("бонус") and "истори" in name: return ChaptersTypes.extra
		if name.startswith("экстра"): return ChaptersTypes.extra

		#---> glossary
		#==========================================================================================#
		if name.startswith("глоссарий"): return ChaptersTypes.glossary

		#---> prologue
		#==========================================================================================#
		if "пролог" in name: return ChaptersTypes.prologue

		#---> trash
		#==========================================================================================#
		if name.startswith("реквизиты") and "переводчик" in name: return ChaptersTypes.trash
		if name.startswith("примечани") and "переводчик" in name: return ChaptersTypes.trash

		#---> chapter
		#==========================================================================================#
		# if "глава" in name: return ChaptersTypes.chapter

		return None

	def __GetBranches(self, data: str):
		"""Получает ветви тайтла."""

		for CurrentBranchData in data["branches"]:
			BranchID = CurrentBranchData["id"]
			ChaptersCount = CurrentBranchData["count_chapters"]
			CurrentBranch = Branch(BranchID)

			for BranchPage in range(0, int(ChaptersCount / 100) + 1):
				Response = self._Requestor.get(f"https://api.{SITE}/api/titles/chapters/?branch_id={BranchID}&count=100&ordering=-index&page=" + str(BranchPage + 1) + "&user_data=1")

				if Response.status_code == 200:
					Data = Response.json["content"]
					
					for CurrentChapter in Data:
						Translators = [sub["name"] for sub in CurrentChapter["publishers"]]
						ChapterObject = Chapter(self._SystemObjects, self._Title)

						ChapterObject.set_id(CurrentChapter["id"])
						ChapterObject.set_volume(CurrentChapter["tome"])
						ChapterObject.set_number(CurrentChapter["chapter"])
						ChapterObject.set_name(CurrentChapter["name"])
						ChapterObject.set_type(self.__CheckChapterType(CurrentChapter["name"]))
						ChapterObject.set_is_paid(CurrentChapter["is_paid"])
						ChapterObject.set_translators(Translators)
						
						if self._Settings.custom["add_free_publication_date"] and CurrentChapter["is_paid"]:
							ChapterObject.add_extra_data("free-publication-date", CurrentChapter["pub_date"])

						CurrentBranch.add_chapter(ChapterObject)

				else: self._Portals.request_error(Response, "Unable to request chapter.")

			self._Title.add_branch(CurrentBranch)		

	def __GetParagraphs(self, chapter: Chapter) -> list[dict]:
		"""
		Получает данные о слайдах главы.
			chapter – данные главы.
		"""

		Paragraphs = list()
		Response = self._Requestor.get(f"https://api.{SITE}/api/titles/chapters/{chapter.id}")

		if Response.status_code == 200:
			Data = Response.json["content"]["content"]
			ParagraphsTags = BeautifulSoup(Data, "html.parser").find_all(["p", "pre"])
			
			for Paragraph in ParagraphsTags:
				
				if Paragraph.name == "pre":
					
					InnerHTML = HTML(str(Paragraph))
					InnerHTML.replace_tag("pre", "blockquote")
					Paragraph = f"<p>{InnerHTML.text}</p>"

				else: 
					Paragraph = str(Paragraph)

				Paragraphs.append(Paragraph)

		elif Response.status_code in [401, 423]: self._Portals.chapter_skipped(self._Title, chapter)
		else: self._Portals.request_error(Response, "Unable to request chapter content.")

		return Paragraphs

	def __GetOriginalLanguage(self, data: dict) -> str:
		"""
		Получает оригинальный язык тайтла.
			data – словарь данных тайтла.
		"""

		OriginalLanguage = None
		TypesDeterminations = {
			"Авторское": "rus",
			"Япония": "jpn",
			"Корея": "kor",
			"Китай": "zho",
			"Запад": "eng"
		}
		SiteType = data["type"]["name"]
		if SiteType in TypesDeterminations.keys(): OriginalLanguage = TypesDeterminations[SiteType]

		return OriginalLanguage

	#==========================================================================================#
	# >>>>> ПУБЛИЧНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#

	def __init__(self, system_objects: SystemObjects, title: Ranobe | None = None):
		"""
		Базовый парсер.
			system_objects – коллекция системных объектов;\n
			title – данные тайтла.
		"""

		#---> Генерация динамических свойств.
		#==========================================================================================#
		self._SystemObjects = system_objects
		self._Title = title
		
		self._Portals = self._SystemObjects.logger.portals
		self._Settings = self._SystemObjects.manager.parser_settings
		self._Requestor = self._InitializeRequestor()

		self._PostInitMethod()

	def amend(self, branch: Branch, chapter: Chapter):
		"""
		Дополняет главу дайными о слайдах.
			branch – данные ветви;\n
			chapter – данные главы.
		"""

		if chapter.is_paid and self._Settings.custom["token"] or not chapter.is_paid:
			Paragraphs = self.__GetParagraphs(chapter)
			for Paragraph in Paragraphs: chapter.add_paragraph(Paragraph)
	
	def parse(self):
		"""Получает основные данные тайтла."""

		Response = self._Requestor.get(f"https://api.{SITE}/api/titles/{self._Title.slug}/")

		if Response.status_code == 200:
			Data = Response.json["content"]
			
			self._Title.set_site(SITE)
			self._Title.set_id(Data["id"])
			self._Title.set_original_language(self.__GetOriginalLanguage(Data))
			self._Title.set_content_language("rus")
			self._Title.set_localized_name(Data["main_name"])
			self._Title.set_eng_name(Data["secondary_name"])
			self._Title.set_another_names(Data["another_name"].split(" / "))
			self._Title.set_covers(self._GetCovers(Data))
			self._Title.set_publication_year(Data["issue_year"])
			self._Title.set_description(self._GetDescription(Data))
			self._Title.set_age_limit(self._GetAgeLimit(Data))
			self._Title.set_status(self._GetStatus(Data))
			self._Title.set_is_licensed(Data["is_licensed"])
			self._Title.set_genres(self._GetGenres(Data))
			self._Title.set_tags(self._GetTags(Data))
			
			self.__GetBranches(Data)

		elif Response.status_code == 404: self._Portals.title_not_found(self._Title)
		else: self._Portals.request_error(Response, "Unable to request title data.")