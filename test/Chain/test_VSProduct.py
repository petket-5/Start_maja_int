#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (C) CNES - All Rights Reserved
This file is subject to the terms and conditions defined in
file 'LICENSE.md', which is part of this source code package.

Author:         Peter KETTIG <peter.kettig@cnes.fr>
Project:        Start_maja, CNES
Created on:     Tue Dec  5 10:26:05 2018
"""

from Unittest import LoggedTestCase
from Unittest import testFunction
from Chain.Product import MajaProduct
from Chain.VSProduct import VenusMuscate, VenusNatif
from os import path

class TestVSProduct(LoggedTestCase.LoggedTestCase):

    prod_vs_nat = ["VE_VM01_VSC_L2VALD_ISRAW906_20180317.DBL.DIR",
                   "VE_OPER_VSC_L1VALD_UNH_20180329.DBL.DIR"]
    prod_vs_mus = ["VENUS-XS_20180201-051359-000_L1C_KHUMBU_C_V1-0",
                   "VENUS_20180201-051359-000_L2A_KHUMBU_C_V1-0",
                   "VENUS-XS_20180201-000000-000_L3A_KHUMBU_C_V1-0"]
    prods_other = ["LANDSAT8-OLITIRS-XSTHPAN_20170501-103532-111_L1C_T31TCH_C_V1-0",
                   "LANDSAT8_20170501-103532-111_L2A_T31TCH_C_V1-0",
                   "LC80390222013076EDC00",
                   "LC08_L1TP_199029_20170527_20170615_01_T1",
                   "L8_TEST_L8C_L2VALD_198030_20130626.DBL.DIR",
                   "S2A_MSIL1C_20170412T110621_N0204_R137_T29RPQ_20170412T111708.SAFE",
                   "S2B_MSIL1C_20180316T103021_N0206_R108_T32TMR_20180316T123927.SAFE",
                   "S2A_OPER_PRD_MSIL1C_PDMC_20161109T171237_R135_V20160924T074932_20160924T081448.SAFE",
                   "S2A_OPER_SSC_L2VALD_36JTT____20160914.DBL.DIR",
                   "S2B_OPER_SSC_L1VALD_21MXT____20180925.DBL.DIR",
                   "SENTINEL2B_20171008-105012-463_L1C_T31TCH_C_V1-0",
                   "SENTINEL2A_20161206-105012-463_L2A_T31TCH_C_V1-0",
                   "SENTINEL2X_20190415-000000-000_L3A_T31UFR_C_V1-1"]

    @classmethod
    def setUpClass(cls):
        """
        Simulate the basic folder + metadata_file structure
        :return:
        """
        import os
        for root in cls.prod_vs_nat:
            os.makedirs(root)
            metadata = root.split(".")[0] + ".HDR"
            testFunction.touch(metadata)
        for root in cls.prod_vs_mus:
            os.makedirs(root)
            metadata = path.join(root, root + "_MTD_ALL.xml")
            testFunction.touch(metadata)

    @classmethod
    def tearDownClass(cls):
        import shutil
        import os
        for root in cls.prod_vs_nat:
            shutil.rmtree(root)
            metadata = root.split(".")[0] + ".HDR"
            os.remove(metadata)
        for root in cls.prod_vs_mus:
            shutil.rmtree(root)

    @testFunction.test_function
    def test_reg_vs_muscate(self):
        tiles = ["KHUMBU", "KHUMBU", "KHUMBU"]
        levels = ["l1c", "l2a", "l3a"]
        dates = ["20180201T051359", "20180201T051359", "20180201T000000"]
        for prod, tile, date, level in zip(self.prod_vs_mus, tiles, dates, levels):
            p = MajaProduct(prod).factory()
            self.assertIsInstance(p, VenusMuscate)
            self.assertEqual(p.get_level(), level)
            self.assertEqual(p.get_platform(), "venus")
            self.assertEqual(p.get_type(), "muscate")
            self.assertEqual(p.get_tile(), tile)
            self.assertEqual(p.get_date().strftime("%Y%m%dT%H%M%S"), date)
            self.assertTrue(path.basename(p.get_metadata_file()).endswith("_MTD_ALL.xml"))
            self.assertTrue(path.exists(p.get_metadata_file()))

        # Other prods:
        for prod in self.prod_vs_nat + self.prods_other:
            p = MajaProduct(prod).factory()
            self.assertNotIsInstance(p, VenusMuscate)

    @testFunction.test_function
    def test_reg_vs_natif(self):
        tiles = ["ISRAW906", "UNH"]
        dates = ["20180317T120000", "20180329T120000"]
        for prod, tile, date in zip(self.prod_vs_nat, tiles, dates):
            p = MajaProduct(prod).factory()
            self.assertIsInstance(p, VenusNatif)
            self.assertEqual(p.get_level(), "l1c")
            self.assertEqual(p.get_platform(), "venus")
            self.assertEqual(p.get_type(), "natif")
            self.assertEqual(p.get_tile(), tile)
            self.assertEqual(p.get_date().strftime("%Y%m%dT%H%M%S"), date)
            self.assertEqual(path.basename(p.get_metadata_file()), prod.split(".")[0] + ".HDR")
            self.assertTrue(path.exists(p.get_metadata_file()))

        # Other prods:
        for prod in self.prod_vs_mus + self.prods_other:
            p = MajaProduct(prod).factory()
            self.assertNotIsInstance(p, VenusNatif)