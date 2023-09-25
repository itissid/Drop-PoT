"""add field column to parsed embedding

Revision ID: 699d88f31ce6
Revises: e306a919aa1d
Create Date: 2023-09-22 18:53:34.362382

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "699d88f31ce6"
down_revision: Union[str, None] = "e306a919aa1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "ParsedEventEmbeddingsTable",
        sa.Column(
            "embedding_type",
            sa.Enum(
                "description", "name", "name_description", name="embedding_type"
            ),
            server_default=sa.text("'description'"),
            nullable=True,
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("ParsedEventEmbeddingsTable", "embedding_type")
    # ### end Alembic commands ###
