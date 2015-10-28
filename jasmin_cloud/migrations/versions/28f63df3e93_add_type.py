"""add_type

Revision ID: 28f63df3e93
Revises: 43de4f4bd19
Create Date: 2015-10-27 14:26:00.204813

"""

# revision identifiers, used by Alembic.
revision = '28f63df3e93'
down_revision = '43de4f4bd19'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


host_type = sa.Enum('bastion-host', 'httpd-host',
                    'analysis-host', 'unmanaged', name='host_type')

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    # Create the enum type first
    host_type.create(op.get_bind(), checkfirst = True)
    # Then add the column
    # We want to add it as NON NULL (i.e. we don't want to use server_default),
    # but we need to set a value
    # The most effective way to do this is to create the column as nullable,
    # set the value, then set the column to non-null
    op.add_column('catalogue_meta', sa.Column('host_type', host_type, nullable = True))
    op.execute("UPDATE catalogue_meta SET host_type='unmanaged'")
    op.alter_column('catalogue_meta', 'host_type', nullable = False)
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    # Drop the column first
    op.drop_column('catalogue_meta', 'host_type')
    # Then drop the type
    host_type.drop(op.get_bind(), checkfirst = True)
    ### end Alembic commands ###