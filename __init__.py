from typing import override

from ..remanga import SourceOperator as ParentSourceOperator

class SourceOperator(ParentSourceOperator):
	"""Source operator."""

	@override
	def _post_init(self):
		"""Execute after instance initialization."""

		pass # Remove parent method body.
