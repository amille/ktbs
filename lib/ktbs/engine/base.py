#    This file is part of KTBS <http://liris.cnrs.fr/sbt-dev/ktbs>
#    Copyright (C) 2011-2012 Pierre-Antoine Champin <pchampin@liris.cnrs.fr> /
#    Universite de Lyon <http://www.universite-lyon.fr>
#
#    KTBS is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    KTBS is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with KTBS.  If not, see <http://www.gnu.org/licenses/>.

"""
I provide the implementation of ktbs:Base .
"""
from rdflib import RDF
from contextlib import contextmanager
import posix_ipc

from .resource import KtbsPostableMixin, KtbsResource
from ..api.base import BaseMixin, InBaseMixin
from ..namespace import KTBS, KTBS_NS_URI


@contextmanager
def get_lock(base_name, timeout=30):
    """Acquire a token from a semaphore for working on a base.

    :param base_name: name of the base, can be an URIRef.
    :param timeout: maximum time to wait on acquire() until a BusyError is raised.
    :type timeout: int or float
    """
    sem_name = str('/' + base_name.replace('/', '-'))
    # Opens the semaphore if it already exists, or create it with an initial value of 1 if it doesn't exist
    base_semaphore = posix_ipc.Semaphore(name=sem_name, flags=posix_ipc.O_CREAT, initial_value=1)
    base_semaphore.acquire(timeout)  # TODO remove the default timeout? NOTE that OS X doesn't support timeout
    try:  # catch exceptions
        yield
    finally:  # make sure we exit properly
        base_semaphore.release()
        # TODO close() the semaphore?


class Base(BaseMixin, KtbsPostableMixin, KtbsResource):
    """I provide the implementation of ktbs:Base .
    """
    ######## ILocalResource (and mixins) implementation  ########

    RDF_MAIN_TYPE = KTBS.Base

    RDF_CREATABLE_IN = [ KTBS.hasBase, ]

    def delete(self, parameters=None, _trust=False):
        """I override :meth:`rdfrest.local.EditableResource.delete`.
        """
        with get_lock(self.uri):
            super(Base, self).delete(parameters, _trust)

    def ack_delete(self, parameters):
        """I override :meth:`rdfrest.util.EditableResource.ack_delete`.
        """
        super(Base, self).ack_delete(parameters)
        root = self.get_root()
        with root.edit(_trust=True) as editable:
            editable.remove((root.uri, KTBS.hasBase, self.uri))
            editable.remove((self.uri, RDF.type, self.RDF_MAIN_TYPE))

    def ack_post(self, parameters, created, new_graph):
        """I override :meth:`rdfrest.util.GraphPostableMixin.ack_post`.
        """
        super(Base, self).ack_post(parameters, created, new_graph)
        with self.edit(_trust=True) as editable:
            editable.add((self.uri, KTBS.contains, created))
            for typ in new_graph.objects(created, RDF.type):
                if typ.startswith(KTBS_NS_URI):
                    assert typ in (KTBS.TraceModel, KTBS.Method,
                                   KTBS.StoredTrace, KTBS.ComputedTrace)
                    editable.add((created, RDF.type, typ))
                    break
            else: # no valid rdf:type was found; should not happen
                assert 0, "No valid rdf:type was found for posted resource"

    def check_deletable(self, parameters):
        """I override :meth:`rdfrest.util.EditableResource.check_deletable`.

        Only an empty base can be deleted.
        """
        diag = super(Base, self).check_deletable(parameters)
        if self.state.value(self.uri, KTBS.contains):
            diag.append("Can not delete non-empty Base")
        return diag

    def find_created(self, new_graph):
        """I override :meth:`rdfrest.util.GraphPostableMixin.find_created`.

        I look for the ktbs:contains property, pointing to something a base
        can contain.
        """
        query = """PREFIX ktbs: <%s>
                   SELECT DISTINCT ?c
                   WHERE { <%s> ktbs:contains ?c .
                           { ?c a ktbs:TraceModel } UNION
                           { ?c a ktbs:Method } UNION
                           { ?c a ktbs:StoredTrace } UNION
                           { ?c a ktbs:ComputedTrace }
                         }
        """ % (KTBS, self.uri)
        return self._find_created_default(new_graph, query)


class InBase(InBaseMixin, KtbsResource):
    """I provide common implementation of all elements contained in a base.
    """
    ######## ILocalResource (and mixins) implementation  ########

    RDF_CREATABLE_IN = [ KTBS.contains, ]

    def ack_delete(self, parameters):
        """I override :meth:`rdfrest.util.DeletableMixin.ack_delete`.
        """
        super(InBase, self).ack_delete(parameters)
        base = self.get_base()
        with base.edit(_trust=True) as editable:
            editable.remove((base.uri, KTBS.contains, self.uri))
            editable.remove((self.uri, RDF.type, self.RDF_MAIN_TYPE))

