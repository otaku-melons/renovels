from typing import override

from remanga import SourceOperator as ParentSourceOperator

from melon.core.base.parser.enums import ContentType

class SourceOperator(ParentSourceOperator):
	"""Source operator."""

	@override
	def _get_content_type_by_slug(self, slug: str) -> ContentType:
		"""
		Get content type by title slug.

		Args:
			slug (str): Title slug.

		Returns:
			ContentType: Content type.
		"""

		return ContentType.Ranobe

	@override
	def _post_init(self):
		"""Execute after instance initialization."""

		pass # Remove parent method body.
