#    This file is part of KTBS <http://liris.cnrs.fr/sbt-dev/ktbs>
#    Copyright (C) 2011 Pierre-Antoine Champin <pchampin@liris.cnrs.fr> /
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
I provide the common implementation of all local KTBS resources.
"""
from rdflib import URIRef
from rdfrest.resource import Resource as RdfRestResource
from rdfrest.mixins import RdfPutMixin, BookkeepingMixin, \
    WithReservedNamespacesMixin, WithCardinalityMixin
from rdfrest.utils import replace_node

from ktbs.common.utils import mint_uri_from_label
from ktbs.namespaces import KTBS, SKOS

class Resource(BookkeepingMixin, WithCardinalityMixin,
               WithReservedNamespacesMixin, RdfPutMixin, RdfRestResource):
    """A KTBS Resource.
    """

    RDF_RESERVED_NS = [KTBS]

    def make_resource(self, uri, node_type=None, graph=None):
        """I make a resource with the given URI.

        NB: the service does not use the `node_type` and `graph` hints.
        """
        # unused argument 'graph' #pylint: disable=W0613
        ret = self.service.get(uri)
        assert isinstance(ret.RDF_MAIN_TYPE ==  node_type)
        return ret

    @classmethod
    def mint_uri(cls, target, new_graph, created):
        """I override :meth:`rdfrest.resource.Resource.mint_uri`.

        I use the skos:prefLabel of the resource to mint a URI, else the class
        name.
        """
        label = new_graph.value(created, SKOS.prefLabel) \
            or cls.__name__.lower()
        return mint_uri_from_label(label, target)

    def _post_or_trust(self, trust, py_class, node, graph):
        """Depending on the value of `trust`, I use rdf_post or I efficiently
        create a resource with `py_class`.

        Note that I nevertheless do ``assert``'s to check the validity of the
        graph, so the efficiency gain may happen only in optimize model.
        """
        if trust:
            if not isinstance(node, URIRef):
                uri = py_class.mint_uri(self, graph, node)
                replace_node(graph, node, uri)
            else:
                uri = node
            assert self.check_posted_graph( #pylint: disable=E1101
                uri, graph) is None         # not a method of every Resource
            # but _post_or_trust will only be used on postable resources...
            assert py_class.check_new_graph(uri, graph) is None
            return py_class.create(self.service, uri, graph)
        else:
            base_uri = self.rdf_post(graph)[0]
            return self.service.get(base_uri)