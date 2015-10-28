"""
This module provides catalogue management functionality for the JASMIN cloud portal.

It uses a combination of cloud services and an SQL database for management of
catalogue items and metadata. `SQLAlchemy <http://www.sqlalchemy.org/>`_ is used
for database access.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"

import uuid
from collections import namedtuple

from sqlalchemy import Column, String, Text, Boolean, Enum
from sqlalchemy.orm.exc import NoResultFound
from pyramid_sqlalchemy import BaseObject, Session

from .cloudservices import CloudServiceError, PermissionsError, NoSuchResourceError
from .util import UUIDType


def includeme(config):
    """
    Configures the Pyramid application for catalogue management.
    
    :param config: Pyramid configurator
    """
    # Add the manager property to the request
    def catalogue(request):
        if request.current_org:
            return CatalogueManager(request.cloud_sessions[request.current_org])
        else:
            return None
    config.add_request_method(catalogue, reify = True)


class _CatalogueMeta(BaseObject):
    """
    SQLAlchemy model for catalogue item metadata.
    """
    __tablename__ = "catalogue_meta"
    
    #: The id of the catalogue item in the system
    id            = Column(UUIDType(), primary_key = True, default = uuid.uuid4)
    #: Uuid of the associated cloud provider image.
    cloud_id      = Column(String(50), nullable = False)
    #: Name of the catalogue item.
    name          = Column(String(200), nullable = False)
    #: The type of the template
    host_type     = Column(Enum('bastion-host',
                                'httpd-host',
                                'analysis-host',
                                'unmanaged', name = 'host_type'),
                                nullable = False, default = 'unmanaged')
    #: Extended description of the catalogue item. Can contain HTML, or be empty.
    description   = Column(Text())
    #: Flag indicating whether machines provisioned using the catalogue item should
    #: have NAT and firewall rules applied to allow inbound traffic from the internet.
    allow_inbound = Column(Boolean(), nullable = False)


class CatalogueItem(namedtuple('CatalogueItemProps',
                               ['id', 'cloud_id', 'name', 'host_type',
                                'description', 'allow_inbound', 'is_public'])):
    """
    Class representing a catalogue item. Properties are *read-only*.
    
    Information is aggregated from :py:class:`.cloudservices.Image` and associated
    metadata to form a complete view of a catalogue item.
    
    .. note::
    
        The system allows multiple catalogue items to be associated with each cloud
        provider image. This allows, for instance, for NATed and non-NATed catalogue
        items derived from the same cloud image.
    
    .. py:attribute:: id
    
        The id of the catalogue item in the system.
    
    .. py:attribute:: cloud_id
    
        Uuid of the associated cloud provider image.
        
    .. py:attribute:: name
    
        Name of the catalogue item.

    .. py:attribute:: host_type
    
        The type of machine that the template provisions.

    .. py:attribute:: description
    
        Extended description of the catalogue item. Can contain HTML, or be empty.
    
    .. py:attribute:: allow_inbound
    
        Flag indicating whether machines provisioned using the catalogue item should
        have NAT and firewall rules applied to allow inbound traffic from the internet.
    
    .. py:attribute:: is_public
    
        Flag indicating whether the catalogue item is public (accessible to all
        organisations) or private (accessible to this organisation only)
    """
    
    
class CatalogueManager:
    """
    Class that is responsible for managing :py:class:`CatalogueItem`\ s.
    
    This implementation uses a combination of vCloud Director API calls and
    metadata stored in an SQL database to build :py:class:`CatalogueItem`\ s.
    
    .. note::
    
        An instance of this class can be accessed as a property of the Pyramid
        request object, i.e. ``r = request.catalogue``.
       
        This property is reified, so it is only evaluated once per request.
       
    :param session: The :py:class:`.cloudservices.Session` to use
    """
    def __init__(self, session):
        self._session = session

    def item_from_machine(self, machine, name, description, allow_inbound):
        """
        Adds a catalogue item using the given machine as a template.
        
        :param machine: The machine to use as a template
        :param name: The name of the new catalogue item
        :param description: Extended description of the new template
        :param allow_inbound: True if the template should allow inbound traffic from
                              the internet, False otherwise
        :returns: The created :py:class:`CatalogueItem`
        """ 
        # First, create the catalogue item in the cloud provider
        image = self._session.image_from_machine(machine.id, name, description)
        # Then create and save a metadata item in the database
        meta = _CatalogueMeta(cloud_id = image.id, name = name,
                              description = description, allow_inbound = allow_inbound)
        sess = Session()
        sess.add(meta)
        sess.flush()
        # Construct the item to return
        return CatalogueItem(meta.id, image.id, meta.name, meta.host_type,
                             meta.description, meta.allow_inbound, image.is_public)

    def delete_item_with_id(self, id):
        """
        Deletes the catalogue item with the given id.
        
        :param id: The id of the catalogue item to delete
        :returns: True on success (raises on failure)
        """
        sess = Session()
        # Because we need to retrieve the cloud_id, we load the item first
        try:
            meta = sess.query(_CatalogueMeta).filter(_CatalogueMeta.id == id).one()
        except NoResultFound:
            # If there is no item with that id, we are done
            return True
        # Delete the metadata entry
        sess.delete(meta)
        sess.flush()
        # If that is successful, check if we need to delete the image in the cloud
        q = sess.query(_CatalogueMeta).filter(_CatalogueMeta.cloud_id == meta.cloud_id)
        if q.count() > 0:
            # If there are still items using the image, we are done
            return True
        # Otherwise, try and delete the image in the cloud provider
        # Even if this fails, the operation is still successful from a user's perspective,
        # so we swallow the errors
        try:
            self._session.delete_image(meta.cloud_id)
        except CloudServiceError:
            pass
        return True

    def available_items(self):
        """
        Retrieves the catalogue items available to the given session.
        
        Access to the catalogue items is controlled by the cloud service (i.e. the
        cloud service is queried for the available items), but only catalogue items
        with an entry in the database are returned.
        
        :returns: List of :py:class:`CatalogueItem`\ s
        """
        # Get the images from the cloud session (let errors bubble)
        images = self._session.list_images()
        # Get the corresponding metadata records
        #   * They might not be in the same order as the images
        #   * There might be more than one for each image
        # Use an IN query so we get them all with one database call
        metas = Session().query(_CatalogueMeta).\
                    filter(_CatalogueMeta.cloud_id.in_([im.id for im in images])).\
                    order_by(_CatalogueMeta.id).\
                    all()
        items = []
        for meta in metas:
            image = next((i for i in images if i.id == meta.cloud_id))
            items.append(
                CatalogueItem(meta.id, image.id, meta.name, meta.host_type,
                              meta.description, meta.allow_inbound, image.is_public)
            )
        return items

    def find_item_by_id(self, id):
        """
        Finds a catalogue item by id.
        
        If no item can be found or the given session doesn't have access, ``None``
        is returned.
        
        :param id: Id of the catalogue item to find
        :returns: :py:class:`CatalogueItem` or ``None``
        """
        try:
            meta = Session().query(_CatalogueMeta).filter(_CatalogueMeta.id == id).one()
            image = self._session.get_image(meta.cloud_id)
            return CatalogueItem(
                meta.id, image.id, meta.name, meta.host_type,
                meta.description, meta.allow_inbound, image.is_public
            )
        except (NoResultFound, PermissionsError, NoSuchResourceError):
            return None