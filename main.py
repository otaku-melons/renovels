from Source.Core.Formats.Ranobe import Branch, Chapter, Ranobe, Statuses
from Source.Core.Base.RanobeParser import RanobeParser
from Source.Core.ImagesDownloader import ImagesDownloader
from Source.Core.Exceptions import TitleNotFound

from dublib.WebRequestor import Protocols, WebConfig, WebLibs, WebRequestor
from dublib.Methods.Data import RemoveRecurringSubstrings, Zerotify
from skimage.metrics import structural_similarity
from dublib.Polyglot import HTML
from bs4 import BeautifulSoup
from skimage import io
from time import sleep

import cv2
import os

#==========================================================================================#
# >>>>> ОПРЕДЕЛЕНИЯ <<<<< #
#==========================================================================================#

VERSION = "1.0.0"
NAME = "renovels"
SITE = "renovels.org"
TYPE = Ranobe

#==========================================================================================#
# >>>>> ОСНОВНОЙ КЛАСС <<<<< #
#==========================================================================================#

class Parser(RanobeParser):
	"""Парсер."""

	#==========================================================================================#
	# >>>>> ПЕРЕОПРЕДЕЛЯЕМЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#

	def _InitializeRequestor(self) -> WebRequestor:
		"""Инициализирует модуль WEB-запросов."""

		Config = WebConfig()
		Config.select_lib(WebLibs.requests)
		Config.set_retries_count(self._Settings.common.retries)
		Config.add_header("Authorization", self._Settings.custom["token"])
		Config.add_header("Referer", f"https://{SITE}/")
		WebRequestorObject = WebRequestor(Config)

		if self._Settings.proxy.enable: WebRequestorObject.add_proxy(
			Protocols.HTTPS,
			host = self._Settings.proxy.host,
			port = self._Settings.proxy.port,
			login = self._Settings.proxy.login,
			password = self._Settings.proxy.password
		)

		return WebRequestorObject
	
	def _PostInitMethod(self):
		"""Метод, выполняющийся после инициализации объекта."""
	
		self.__CoversRequestor = self.__InitializeCoversRequestor()

	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#

	def __InitializeCoversRequestor(self) -> WebRequestor:
		"""Инициализирует модуль WEB-запросов обложек."""

		Config = WebConfig()
		Config.select_lib(WebLibs.requests)
		Config.set_retries_count(self._Settings.common.retries)
		Config.requests.enable_proxy_protocol_switching(True)
		Config.add_header("Referer", f"https://{SITE}/")
		WebRequestorObject = WebRequestor(Config)

		if self._Settings.proxy.enable: WebRequestorObject.add_proxy(
			Protocols.HTTPS,
			host = self._Settings.proxy.host,
			port = self._Settings.proxy.port,
			login = self._Settings.proxy.login,
			password = self._Settings.proxy.password
		)

		return WebRequestorObject

	def __CheckForStubs(self) -> bool:
		"""Проверяет, является ли обложка заглушкой."""

		FiltersDirectories = os.listdir(f"Parsers/{NAME}/Filters")

		for FilterIndex in FiltersDirectories:
			Patterns = os.listdir(f"Parsers/{NAME}/Filters/{FilterIndex}")
			
			for Pattern in Patterns:
				Result = self.__CompareImages(f"Parsers/{NAME}/Filters/{FilterIndex}/{Pattern}")
				if Result != None and Result < 50.0: return True
		
		return False

	def __Collect(self, filters: str | None = None, pages: int | None = None) -> list[str]:
		"""
		Собирает список тайтлов по заданным параметрам.
			filters – строка из URI каталога, описывающая параметры запроса;\n
			pages – количество запрашиваемых страниц.
		"""

		Slugs = list()
		IsCollected = False
		Page = 1
		
		while not IsCollected:
			Response = self._Requestor.get(f"https://api.{SITE}/api/search/catalog/?page={Page}&count=30&ordering=-id&{filters}")
			
			if Response.status_code == 200:
				self._PrintCollectingStatus(Page)
				PageContent = Response.json["content"]
				for Note in PageContent: Slugs.append(Note["dir"])
				if not PageContent or pages and Page == pages: IsCollected = True
				Page += 1
				sleep(self._Settings.common.delay)

			else:
				self._SystemObjects.logger.request_error(Response, "Unable to request catalog.")
				raise Exception("Unable to request catalog.")

		return Slugs
	
	def __CollectUpdates(self, period: int | None = None, pages: int | None = None) -> list[str]:
		"""
		Собирает список обновлений тайтлов по заданным параметрам.
			period – количество часов до текущего момента, составляющее период получения данных;\n
			pages – количество запрашиваемых страниц.
		"""

		Slugs = list()
		period *= 3_600_000
		IsCollected = False
		Page = 1
		
		while not IsCollected:
			Response = self._Requestor.get(f"https://api.{SITE}/api/titles/last-chapters/?page={Page}&count=30")
			
			if Response.status_code == 200:
				self._PrintCollectingStatus(Page)
				PageContent = Response.json["content"]

				for Note in PageContent:

					if not period or Note["upload_date"] <= period:
						Slugs.append(Note["dir"])

					else:
						Slugs = list(set(Slugs))
						IsCollected = True
						break
					
				if not PageContent or pages and Page == pages: IsCollected = True
				if IsCollected: self._SystemObjects.logger.titles_collected(len(Slugs))
				Page += 1
				sleep(self._Settings.common.delay)

			else:
				self._SystemObjects.logger.request_error(Response, "Unable to request catalog.")
				raise Exception("Unable to request catalog.")

		return Slugs

	def __CompareImages(self, pattern_path: str) -> float | None:
		"""
		Сравнивает изображение с фильтром.
			url – ссылка на обложку;\n
			pattern_path – путь к шаблону.
		"""

		Differences = None

		try:
			Temp = self._SystemObjects.temper.get_parser_temp(NAME)
			Pattern = io.imread(f"{Temp}/cover")
			Image = cv2.imread(pattern_path)
			Pattern = cv2.cvtColor(Pattern, cv2.COLOR_BGR2GRAY)
			Image = cv2.cvtColor(Image, cv2.COLOR_BGR2GRAY)
			PatternHeight, PatternWidth = Pattern.shape
			ImageHeight, ImageWidth = Image.shape
		
			if PatternHeight == ImageHeight and PatternWidth == ImageWidth:
				(Similarity, Differences) = structural_similarity(Pattern, Image, full = True)
				Differences = 100.0 - (float(Similarity) * 100.0)

		except Exception as ExceptionData:
			self._SystemObjects.logger.error("Problem occurred during filtering stubs: \"" + str(ExceptionData) + "\".")		
			Differences = None

		return Differences

	def __GetAgeLimit(self, data: dict) -> int:
		"""
		Получает возрастной рейтинг.
			data – словарь данных тайтла.
		"""

		Ratings = {
			0: 0,
			1: 16,
			2: 18
		}
		Rating = Ratings[data["age_limit"]]

		return Rating 

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
						Buffer = {
							"id": CurrentChapter["id"],
							"volume": str(CurrentChapter["tome"]),
							"number": CurrentChapter["chapter"],
							"name": Zerotify(CurrentChapter["name"]),
							"is_paid": CurrentChapter["is_paid"],
							"free-publication-date": None,
							"translators": Translators,
							"paragraphs": []	
						}
						
						if self._Settings.custom["add_free_publication_date"]:
							if Buffer["is_paid"]: Buffer["free-publication-date"] = CurrentChapter["pub_date"]

						else:
							del Buffer["free-publication-date"]

						ChapterObject = Chapter(self._SystemObjects, self._Title)
						ChapterObject.set_dict(Buffer)
						CurrentBranch.add_chapter(ChapterObject)

				else: self._SystemObjects.logger.request_error(Response, "Unable to request chapter.")

			self._Title.add_branch(CurrentBranch)		

	def __GetCovers(self, data: dict) -> list[str]:
		"""Получает список обложек."""

		Covers = list()

		for CoverURI in data["img"].values():

			if CoverURI not in ["/media/None"]:
				Buffer = {
					"link": f"https://api.{SITE}{CoverURI}",
					"filename": CoverURI.split("/")[-1]
				}

				if self._Settings.common.sizing_images:
					Buffer["width"] = None
					Buffer["height"] = None

				Covers.append(Buffer)

				if self._Settings.custom["unstub"]:
					ImagesDownloader(self._SystemObjects, self.__CoversRequestor).temp_image(
						url = Buffer["link"],
						filename = "cover"
					)
					
					if self.__CheckForStubs():
						Covers = list()
						self._SystemObjects.logger.covers_unstubbed(self._Title.slug, self._Title.id)
						break

		return Covers

	def __GetDescription(self, data: dict) -> str | None:
		"""
		Получает описание.
			data – словарь данных тайтла.
		"""

		Description = None
		Description = HTML(data["description"]).plain_text
		Description = Description.replace("\r", "").replace("\xa0", " ").strip()
		Description = RemoveRecurringSubstrings(Description, "\n")
		Description = Zerotify(Description)

		return Description

	def __GetGenres(self, data: dict) -> list[str]:
		"""
		Получает список жанров.
			data – словарь данных тайтла.
		"""

		Genres = list()
		for Genre in data["genres"]: Genres.append(Genre["name"])

		return Genres

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

		elif Response.status_code in [401, 423]:
			self._SystemObjects.logger.chapter_skipped(self._Title, chapter)

		else:
			self._SystemObjects.logger.request_error(Response, "Unable to request chapter content.")

		return Paragraphs

	def __GetStatus(self, data: dict) -> str:
		"""
		Получает статус.
			data – словарь данных тайтла.
		"""

		Status = None
		StatusesDetermination = {
			"Продолжается": Statuses.ongoing,
			"Закончен": Statuses.completed,
			"Анонс": Statuses.announced,
			"Заморожен": Statuses.dropped,
			"Нет переводчика": Statuses.dropped,
			"Не переводится (лицензировано)": Statuses.dropped
		}
		SiteStatusIndex = data["status"]["name"]
		if SiteStatusIndex in StatusesDetermination.keys(): Status = StatusesDetermination[SiteStatusIndex]

		return Status

	def __GetTags(self, data: dict) -> list[str]:
		"""
		Получает список тегов.
			data – словарь данных тайтла.
		"""

		Tags = list()
		for Tag in data["categories"]: Tags.append(Tag["name"])

		return Tags

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

	def amend(self, branch: Branch, chapter: Chapter):
		"""
		Дополняет главу дайными о слайдах.
			branch – данные ветви;\n
			chapter – данные главы.
		"""

		Paragraphs = self.__GetParagraphs(chapter)
		for Paragraph in Paragraphs: chapter.add_paragraph(Paragraph)

	def collect(self, period: int | None = None, filters: str | None = None, pages: int | None = None) -> list[str]:
		"""
		Собирает список тайтлов по заданным параметрам.
			period – количество часов до текущего момента, составляющее период получения данных;\n
			filters – строка из URI каталога, описывающая параметры запроса;\n
			pages – количество запрашиваемых страниц.
		"""

		if filters and not period:
			self._SystemObjects.logger.collect_filters(filters)

		elif filters and period:
			self._SystemObjects.logger.collect_filters_ignored()
			self._SystemObjects.logger.collect_period(period)

		if pages:
			self._SystemObjects.logger.collect_pages(pages)

		Slugs: list[str] = self.__Collect(filters, pages) if not period else self.__CollectUpdates(period, pages)

		return Slugs
	
	def parse(self):
		"""Получает основные данные тайтла."""

		Response = self._Requestor.get(f"https://api.{SITE}/api/titles/{self._Title.slug}/")

		if Response.status_code == 200:
			Data = Response.json["content"]
			
			self._Title.set_site(SITE)
			self._Title.set_id(Data["id"])
			self._SystemObjects.logger.parsing_start(self._Title)
			self._Title.set_original_language(self.__GetOriginalLanguage(Data))
			self._Title.set_content_language("rus")
			self._Title.set_localized_name(Data["main_name"])
			self._Title.set_eng_name(Data["secondary_name"])
			self._Title.set_another_names(Data["another_name"].split(" / "))
			self._Title.set_covers(self.__GetCovers(Data))
			self._Title.set_publication_year(Data["issue_year"])
			self._Title.set_description(self.__GetDescription(Data))
			self._Title.set_age_limit(self.__GetAgeLimit(Data))
			self._Title.set_status(self.__GetStatus(Data))
			self._Title.set_is_licensed(Data["is_licensed"])
			self._Title.set_genres(self.__GetGenres(Data))
			self._Title.set_tags(self.__GetTags(Data))
			
			self.__GetBranches(Data)

		elif Response.status_code == 404: raise TitleNotFound(self._Title)
		else: self._SystemObjects.logger.request_error(Response, "Unable to request title data.", exception = True)