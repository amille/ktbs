# -*- coding: utf-8 -*-

#    This file is part of KTBS <http://liris.cnrs.fr/sbt-dev/ktbs>
#    Copyright (C) 2011-2012 Pierre-Antoine Champin <pchampin@liris.cnrs.fr> /
#    Françoise Conil <francoise.conil@liris.cnrs.fr> /
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

from ktbs.namespace import KTBS

from .test_ktbs_engine import KtbsTestCase


class TestFusion(KtbsTestCase):

    def test_fusion(self):
        base = self.my_ktbs.create_base("b/")
        model = base.create_model("m")
        otype = model.create_obsel_type("#ot")
        origin = "orig-abc"
        src1 = base.create_stored_trace("s1/", model, origin=origin,
                                        default_subject="alice")
        src2 = base.create_stored_trace("s2/", model, origin=origin,
                                        default_subject="bob")
        ctr = base.create_computed_trace("ctr/", KTBS.fusion, {},
                                         [src1, src2],)

        assert ctr.model == model
        assert ctr.origin == origin
        assert len(ctr.obsels) == 0

        o10 = src1.create_obsel("o10", otype, 0)
        assert len(ctr.obsels) == 1
        o21 = src2.create_obsel("o21", otype, 10)
        assert len(ctr.obsels) == 2
        o12 = src1.create_obsel("o12", otype, 20)
        assert len(ctr.obsels) == 3
        o23 = src2.create_obsel("o23", otype, 30)
        assert len(ctr.obsels) == 4
        o11 = src1.create_obsel("o11", otype, 10)
        assert len(ctr.obsels) == 5
        o20 = src2.create_obsel("o20", otype, 0)
        assert len(ctr.obsels) == 6

        with src1.obsel_collection.edit() as editable:
            editable.remove((o10.uri, None, None))
        assert len(ctr.obsels) == 5

        with src2.obsel_collection.edit() as editable:
            editable.remove((o21.uri, None, None))
        assert len(ctr.obsels) == 4
