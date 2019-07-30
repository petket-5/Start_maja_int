#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (C) CNES - All Rights Reserved
This file is subject to the terms and conditions defined in
file 'LICENSE.md', which is part of this source code package.

Author:         Peter KETTIG <peter.kettig@cnes.fr>
Project:        Start_maja, CNES
Created on:     Tue Dec  4 09:26:05 2018
"""

import os
import sys
import re
import logging


class StartMaja(object):
    """
    Run the MAJA processor
    """
    version = "3.0.1"
    date_regex = r"\d{4}-\d{2}-\d{2}"  # YYYY-MM-DD
    regS2 = [r"^S2[AB]_MSIL1C_\d+T\d+_N\d+_R\d+_TXXXXX_\d+T\d+.SAFE$",
             r"^SENTINEL2[AB]_[-\d]+_L(1C|2A)_TXXXXX_\w_V[\d-]+$",
             r"^S2[AB]_OPER_SSC_L[12]VALD_XXXXX_\w+.HDR$",
             r"^S2[AB]_OPER_PRD_MSIL1C_PDMC_\w+_R\d+_V\w+.SAFE$"]
    regL8 = [r"^LC08_L\w+",
             r"^LC8\w+$",
             r"^LANDSAT8-[\w-]+_[-\d]+_L(1C|2A)_TXXXXX_\w_V[\d-]+$",
             r"^L8_\w{4}_L8C_L[12]VALD_[\d_]+.HDR$"]
    regVns = [r"^VENUS-XS_[-\d]+_L(1C|2A)_XXXXX_\w_V\w+",
              r"^VE_\w{4}_VSC_L[12]VALD_\w+.HDR$"]
    regCAMS = r"\w{3}_TEST_EXO_CAMS_\w+"
    regDTM = r"\w+_AUX_REFDE2_\w*"
    regGIPP = [r"\w+GIP_" + gipp + "\w+" for gipp in ["L2ALBD",
                                                      "L2DIFT",
                                                      "L2DIRT",
                                                      "L2TOCR",
                                                      "L2WATV"]] +\
              [r"\w+GIP_" + gipp + "\w+" for gipp in ["CKEXTL",
                                                      "CKQLTL",
                                                      "L2COMM",
                                                      "L2SITE",
                                                      "L2SMAC"]]
    
    current_dir = os.path.dirname(os.path.realpath(__file__))

    def __init__(self, input_dirs, gipp, tile, site, folder, dtm, start, end, overwrite, nbackward, verbose):
        """
        Init the instance using the old start_maja parameters
        """
        from Common import DateConverter
        self.verbose = verbose
        logging_level = logging.DEBUG if self.str2bool(self.verbose) else logging.INFO
        self.init_loggers(msg_level=logging_level)
        logging.info("=============This is Start_Maja v%s==============" % self.version)
        
        self.input_dirs = input_dirs
        logging.debug("Checking GIPP files")
        if not os.path.isdir(gipp):
            raise OSError("Cannot find GIPP folder: %s" % gipp)
        for regGIPP in self.regGIPP:
            if not [f for f in os.listdir(gipp) if re.search(regGIPP, f)]:
                raise OSError("Missing GIPP file: %s" % regGIPP)
        self.gipp = gipp
        logging.debug("...found %s" % gipp)
        
        if tile[0] == "T" and len(tile) == 6 and tile[1:2].isdigit():
            self.tile = tile[1:]  # Remove the T from e.g. T32ABC
        else:
            self.tile = tile
        self.site = site
        if not self.site:
            logging.info("No site specified. Searching for product directly by TileID")
        if not os.path.isfile(folder):
            raise OSError("Cannot find folder definition file!")
        self.folder = folder
        self.dtm = self.get_dtm_files(dtm)
        if re.search(self.date_regex, start):
            self.start = DateConverter.stringToDatetime(start.replace("-", ""))
        else:
            raise ValueError("Unknown date encountered: %s" % start)
        if re.search(self.date_regex, end):
            self.end = DateConverter.stringToDatetime(end.replace("-", ""))
        else:
            raise ValueError("Unknown date encountered: %s" % end)
        if self.start > self.end:
            raise ValueError("Start date has to be before the end date!")
        self.userconf = os.path.join(self.current_dir, "userconf")
        # Subtract 1, which means including the actual product:
        self.nbackward = nbackward - 1
        self.overwrite = self.str2bool(overwrite)
            
        return
    
    @staticmethod
    def str2bool(v):
        """
        Returns a boolean following a string input
        :param v: String to be tested if it"s containing a True/False value
        :return: True, if string contains ("yes", "true", "t", "y", "1"), false if not
        """
        if v.lower() in ("yes", "true", "t", "y", "1"):
            return True
        elif v.lower() in ("no", "false", "f", "n", "0"):
            return False
        raise argparse.ArgumentTypeError("Boolean value expected.")

    def init_loggers(self, msg_level=logging.DEBUG, filepath=""):
        """
        Init a file and a stdout logger
        :param msg_level: Standard msgLevel for both loggers. Default is DEBUG
        :param filepath: The path to save the log-file to. If empty, no log-to-file will be done"
        """
        
        filename = "Start_Maja.log"

        # Create default path or get the pathname without the extension, if there is one
        logger = logging.getLogger()
        logger.handlers = []  # Remove the standard handler again - Bug in logging module
       
        logger.setLevel(msg_level)
        formatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s] %(message)s")
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Currently deactivated
        if filepath is not "":
            dbg_full_path = os.path.join(filepath, filename)
            print("Logging to file " + dbg_full_path)
            self.create_directory(filepath)
            file_handler = logging.FileHandler(dbg_full_path)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        return logger
    
    def get_dtm_files(self, dtm_dir):
        """
        Find DTM folder for tile and search for associated HDR and DBL files
        A DTM folder has the following naming structure:
            S2__TEST_AUX_REFDE2_TILEID_0001 with TILEID e.g. T31TCH, KHUMBU ...
        Inside the folder, a single .HDR file and an associated .DBL.DIR file
        has to be found. OSError is thrown otherwise.
        :param dtm_dir: The directory containing the DTM folder.
        """
        logging.debug("Searching for DTM")
        if dtm_dir is None:
            logging.info("No DTM specified. Searching for DTM in %s" % self.current_dir)
            dtm_dir = self.current_dir
            
        hdr_files, dbl_files = [], []
        for f in os.listdir(os.path.join(dtm_dir)):
            if re.search(self.regDTM + self.tile + "\w*" + ".HDR", os.path.basename(f)):
                hdr_files.append(os.path.join(dtm_dir, f))
            if re.search(self.regDTM + self.tile + "\w*" + ".DBL", os.path.basename(f)):
                dbl_files.append(os.path.join(dtm_dir, f))
        if len(hdr_files) == 1 and len(dbl_files) >= 1:
            logging.debug("...found %s" % os.path.basename(hdr_files[0]))
            return hdr_files + dbl_files
        
        # If not found yet, search for folder with the same name:
        hdr_files, dbl_files = [], []
        dtm_folder = [f for f in os.listdir(dtm_dir) if re.search(self.regDTM + self.tile + "\w+", os.path.basename(f))]        
        if len(dtm_folder) != 1:
            raise OSError("Error finding DTM folder for %s in %s" % (self.tile, dtm_dir))
        for f in os.listdir(os.path.join(dtm_dir, dtm_folder[0])):
            if re.search(self.regDTM + self.tile + "\w*" + ".HDR", os.path.basename(f)):
                hdr_files.append(os.path.join(dtm_dir, dtm_folder[0], f))
            if re.search(self.regDTM + self.tile + "\w*" + ".DBL", os.path.basename(f)):
                dbl_files.append(os.path.join(dtm_dir, dtm_folder[0], f))
        if len(hdr_files) != 1:
            raise OSError("More than one .HDR file found for DTM %s in %s" % (self.tile, dtm_dir))
        dtm = [os.path.join(dtm_dir, dtm_folder[0], f) for f in hdr_files + dbl_files]
        logging.debug("...found %s" % os.path.basename(hdr_files[0]))
        return dtm
    
    def read_folders_file(self, cfg_file):
        """
        Read contents of the folders.txt file containing at least the config params:
            repWork, repL1, repL2 and exeMaja
        :param cfg_file: The path to the file
        """
        import configparser
        import os
        # Parsing configuration file
        config = configparser.ConfigParser()
        config.read(cfg_file)
    
        # get cfg parameters
        rep_work = config.get("PATH", "repWork")
        if not os.path.isdir(rep_work):
            raise OSError("repWork is missing: %s" % rep_work)
        rep_l1 = config.get("PATH", "repL1")
        rep_l2 = config.get("PATH", "repL2")
        exe_maja = config.get("PATH", "exeMaja")
        if not os.path.isfile(exe_maja):
            raise OSError("exeMaja is missing: %s" % exe_maja)
        # CAMS is optional:
        try:
            rep_cams = config.get("PATH", "repCAMS")
            if not os.path.isdir(rep_cams):
                raise OSError("repCAMS is missing: %s" % rep_cams)
        except configparser.NoOptionError:
            logging.warning("repCAMS is missing. Processing without CAMS")
            rep_cams = None
        
        return rep_work, rep_l1, rep_l2, exe_maja, rep_cams
    
    @staticmethod
    def set_input_directories(prod_l1, prod_l2, input_dirs):
        """
        Set the L1 and L2 product directory paths. If input_dirs is set, it
        overloads first the L1C directory, then the L2A directory
        """
        if not input_dirs:
            if not os.path.isdir(prod_l1):
                raise OSError("repL1 is missing: %s" % prod_l1)
            if not os.path.isdir(prod_l2):
                raise OSError("repL2 is missing: %s" % prod_l2)
            return prod_l1, prod_l2
        
        if len(input_dirs) == 1:
            if not os.path.exists(input_dirs[0]):
                raise OSError("Cannot find L1C directory: %s" % input_dirs[0])
            if not os.path.isdir(prod_l2):
                raise OSError("repL2 is missing: %s" % prod_l2)
            return input_dirs[0], prod_l2
        elif len(input_dirs) == 2:
            if not os.path.exists(input_dirs[0]):
                raise OSError("Cannot find L1C directory: %s" % input_dirs[0])
            if not os.path.exists(input_dirs[1]):
                raise OSError("Cannot find L2A directory: %s" % input_dirs[1])
            return input_dirs[0], input_dirs[1]
        
        raise ValueError("More than two input directories given: %s" % input_dirs)
        
    def get_cams_files(self, cams_dir):
        """
        Find CAMS folder and search for associated HDR and DBL files
        A CAMS folder has the following naming structure:
            MMM_TEST_EXO_CAMS_YYYYMMDDThhmmss_YYYYMMDDThhmmss
            with MMM = mission (e.g. S2_)
        Inside the folder, a single .HDR file and an associated .DBL.DIR/.DBL file
        has to be found. OSError is thrown otherwise.
        :param cams_dir: The directory containing the CAMS folder.
        """
        hdr_files, dbl_files = [], []
        if not cams_dir:
            return []
        logging.debug("Searching for CAMS")
        for f in os.listdir(cams_dir):
            if re.search(self.regCAMS + ".HDR", os.path.basename(f)):
                hdr_files.append(os.path.join(cams_dir, f))
            if re.search(self.regCAMS + ".DBL", os.path.basename(f)):
                dbl_files.append(os.path.join(cams_dir, f))
        if len(hdr_files) > len(dbl_files):
            raise OSError("One or more CAMS HDR files imcomplete: #HDR=%s, #DBL=%s"
                          % (len(hdr_files), len(dbl_files)))
        cams = hdr_files + dbl_files
        logging.debug("...found %s CAMS files" % len(hdr_files))
        return cams
    
    @staticmethod
    def filter_cams(cams_files, start_date, end_date):
        """
        Filter out all CAMS files if they are between the given start_date and end_date
        """
        from Common import DateConverter as dc
        cams_filtered = []
        for cams in cams_files:
            date = dc.getCAMSDate(cams)
            if date <= start_date or date >= end_date:
                cams_filtered.append(cams)
        return cams_filtered
    
    @staticmethod
    def get_specifier(site, tile):
        """
        Determine whether the products are ordered by site and tile or only by tile
        """
        if not site:
            specifier = tile
        else:
            specifier = site
        return specifier
    
    @staticmethod
    def get_platform_products(input_dir, tile, reg):
        """
        Get the available products for a given platform regex
        """
        prods = []
        if not os.path.isdir(input_dir):
            return prods
        for prod in os.listdir(input_dir):
            for i, pattern in enumerate(reg):
                if re.search(re.compile(pattern.replace("XXXXX", tile)), prod):
                    prods.append((os.path.join(input_dir, prod), i))
        return prods
    
    def get_all_products(self, site, tile, rep_l1, rep_l2, input_dirs):
        """
        Get all available L1 and L2 products for the tile and site
        """
        prev_l1, prev_l2 = [], []
        platform_id = -1
        specifier = self.get_specifier(site, tile)
        input_rep_l1 = os.path.join(rep_l1, specifier)
        input_rep_l2 = os.path.join(rep_l2, specifier)
        input_dir_l1, input_dir_l2 = self.set_input_directories(input_rep_l1, input_rep_l2, input_dirs)
        for i, platform in enumerate([self.regS2, self.regL8, self.regVns]):
            rep_l1_filtered = self.get_platform_products(input_dir_l1, tile, platform)
            rep_l2_filtered = self.get_platform_products(input_dir_l2, tile, platform)
            if rep_l1_filtered and not prev_l1:
                platform_id = i
                prev_l1 = rep_l1_filtered
                prev_l2 = rep_l2_filtered
            elif rep_l1_filtered and prev_l1 or rep_l2_filtered and prev_l2:
                raise OSError("Products for multiple platforms found: %s, %s" % (prev_l1, prev_l2))
        if not prev_l1:
            raise OSError("Cannot find L1 products for site %s or tile %s in %s"
                          % (site, tile, rep_l1))
        if not prev_l2:
            logging.debug("No L2 products found.")
            
        return prev_l1, prev_l2, platform_id
    
    @staticmethod
    def filter_products_by_date(prods_l1, prods_l2, platform, start_date, end_date, nbackward):
        """
        Filter out all products if they are between the given start_date and end_date
        """
        from Common import DateConverter as dc
        prods_l1_filtered, prods_l2_filtered = [], []
        print(prods_l1)
        print(prods_l2)
        # Get the first available L1 product for the current start date
        process_l1 = [dc.getDateFromProduct(d, platform) for d in prods_l1 if dc.getDateFromProduct(d, platform) >= start_date]
        if not process_l1:
            raise ValueError("No products found after start date %s" % dc.datetimeToString(start_date))
        start_l1 = sorted(process_l1)[0]
        # Get products before this date
        prev_l1 = [d for d in prods_l1 if dc.getDateFromProduct(d, platform) < start_l1]
        prev_l2 = [d for d in prods_l2 if dc.getDateFromProduct(d, platform) < start_l1]
        if prev_l2:
            mode = ["NOMINAL"]
        elif prev_l1:
            mode = ["BACKWARD"]
            if len(prev_l1) < nbackward:
                logging.warning("Less than %s L1 products found for the %s mode" % (nbackward, mode[0]))
        elif not prev_l1:
            mode = ["INIT"]
            logging.warning("Missing previous L2 products. Will begin with INIT mode")
        else:
            raise ValueError("Unknown configuration encountered with products %s %s", prev_l1, prev_l2)
        print(mode)
        exit(1)
        for prod in prods_l1:
            d = dc.getDateFromProduct(prod, platform)
            if start_date <= d <= end_date:
                prods_l1_filtered.append(prod)
        for prod in prods_l2:
            d = dc.getDateFromProduct(prod, platform)
            if start_date <= d <= end_date:
                prods_l2_filtered.append(prod)
        if len(prods_l1_filtered) == 0:
            raise ValueError("No L1 products between %s and %s" %
                             (dc.datetimeToStringShort(start_date),
                              dc.datetimeToStringShort(end_date)))
        
        return prods_l1_filtered, prods_l2_filtered
    
    def create_workplans(self, prods_l1, prods_l2, platform, tile, CAMS, DTM, start_date, conf, end_date, n_backward):
        """
        Create a workplan for each Level-1 product found between the given date period
        For the first product available, check on top if an L2 product from the date
        before is present to run in NOMINAL.
        If not, check if there are at minimum n_backward products to run
        a BACKWARD processing.
        If both of those conditions are not met, a simple INIT is run and the rest
        in NOMINAL
        :param prods_l1: All L1 products found
        :param prods_l2: All L2 products found
        :param platform: The platform of the L1 and L2 products
        :param start_date: Beginning of the desired processing period
        :param end_date: End of the desired processing period
        :param n_backward: Minimum number of products to be used for a BACKWARD mode
        :return: List of workplans to be executed
        """
        from Common import DateConverter as dc
        from Chain import Workplan as wp
        
        # Create list of L2 and L1 products with their respective date:
        dates_l2 = sorted([(dc.getDateFromProduct(prod, platform), prod) for prod in prods_l2], key=lambda tup: tup[0])
        dates_l1 = sorted([(dc.getDateFromProduct(prod, platform), prod) for prod in prods_l1], key=lambda tup: tup[0])
        
        # Filter out all L1 products before the start_date:
        dates_l1filtered = [(date, prod) for date, prod in dates_l1 if date > start_date]
        if len(dates_l1) - len(dates_l1filtered) > 0:
            logging.info("Discarding %s products older than the start date %s" %
                         (len(dates_l1) - len(dates_l1filtered), dc.datetimeToStringShort(start_date)))
        
        workplans = []
        # First product: Check if L2 existing, if not check if BACKWARD possible:
        date_l1 = dc.getDateFromProduct(dates_l1filtered[0][1], platform)
        if date_l1 > end_date:
            raise ValueError("No workplan can be created for the chosen period %s to %s" %
                             (dc.datetimeToStringShort(start_date), dc.datetimeToStringShort(end_date)))
        prod_l2 = dc.findPreviousL2Product(dates_l2, date_l1)
        past_l1 = dc.findNewerProducts(dates_l1filtered, date_l1)
        if prod_l2:
            workplans.append(wp.ModeNominal(date=dates_l1filtered[0][0],
                                            L1=dates_l1filtered[0][1],
                                            L2=prod_l2[0][1],
                                            CAMS=CAMS,
                                            DTM=DTM,
                                            tile=tile,
                                            conf=conf
                                            ))
        elif len(past_l1) >= n_backward:
            logging.warning("No previous L2 product found. Beginning in BACKWARD mode")
            workplans.append(wp.ModeBackward(date=dates_l1filtered[0][0],
                                             L1=[dates_l1filtered[0][1]] + [prod for date, prod in past_l1[:n_backward]],
                                             L2=None,
                                             CAMS=CAMS,
                                             DTM=DTM,
                                             tile=tile,
                                             conf=conf
                                             ))
        else:
            print("Test1", dates_l1filtered[0])
            # If both fail, go for an INIT mode and log a warning:
            logging.warning("Less than %s _l1 products found. Beginning in INIT mode" % n_backward)
            workplans.append(wp.ModeInit(date=dates_l1filtered[0][0],
                                         L1=dates_l1filtered[0][1],
                                         L2=None,
                                         CAMS=CAMS,
                                         DTM=DTM,
                                         tile=tile,
                                         conf=conf
                                         ))
        # For the rest: Setup NOMINAL
        for date, prod in dates_l1filtered[1:]:
            if date > end_date:
                continue
            workplans.append(wp.ModeNominal(date=date,
                                            L1=prod,
                                            L2=None,
                                            CAMS=CAMS,
                                            DTM=DTM,
                                            tile=tile,
                                            conf=conf,
                                            checkL2=True
                                            ))
        
        # This should never happen:
        if not workplans:
            raise ValueError("No workplans created!")
        
        return workplans

    def run(self):
        """
        Run the whole artillery:
            - Find all L1 and L2 products
            - Find all CAMS files
            - Filter both by start and end dates, if there are
            - Determine the Workplans and a mode for each (INIT, BACKWARD, NOMINAL)
            - For each workplan:
            -   Create the input directory and link all the needed inputs
            -   Create the output directory
            -   Run MAJA
        """
        from Common import FileSystem
        rep_work, rep_l1, rep_l2, exeMaja, repCAMS = self.read_folders_file(self.folder)
        availProdsL1, availProdsL2, platform = self.get_all_products(self.site, self.tile, rep_l1, rep_l2, self.input_dirs)
        availCAMS = self.get_cams_files(repCAMS)
        cams = self.filter_cams(availCAMS,self.start, self.end)
        workplans = self.create_workplans(prods_l1=availProdsL1, prods_l2=availProdsL2, platform=platform, CAMS=cams,
                                          DTM=self.dtm, tile=self.tile, conf=self.userconf, start_date=self.start,
                                          end_date=self.end, n_backward=self.nbackward)
        logging.info("%s workplan(s) successfully created:" % len(workplans))
        # Print without the logging-formatting:
        print(str("%8s | %5s | %8s | %70s | %15s" % ("DATE", "TILE", "MODE", "L1-PRODUCT", "INFO/L2-PRODUCT")))
        for wp in workplans:
            print(wp)
#            input_dir = self.createInputDir(rep_work, wp.productsL1 + wp.productsL2, cams, self.dtm, self.gipp)
#            specifier = self.getSpecifier(self.site, self.tile)
#            output_dir = os.path.join(rep_l2, specifier)
#            if(not os.path.exists(output_dir)):
#                FileSystem.createDirectory(output_dir)
#            wp.execute(exeMaja, input_dir, output_dir, self.tile, self.userconf, self.verbose)
#            FileSystem.removeDirectory(input_dir)
        logging.info("=============Start_Maja v%s finished=============" % self.version)

        pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", "--gipp", help="Name of the GIPP folder to be used", type=str, required=True)
    parser.add_argument("-t", "--tile", help="Tile number", type=str, required=True)
    parser.add_argument("-i", "--input", help="Product input directory list. This OVERLOADS the L1C dir (and if given) the L2C dir!", nargs="+", required=False)
    parser.add_argument("-s", "--site", help="Site name. If not specified, the tile number is used directly for finding the L1/L2 product", type=str, required=False)
    parser.add_argument("-f", "--folder", type=str, help="Folder definition file", required=True)
    parser.add_argument("-m", "--dtm", type=str, help="DTM folder. If none is specified, it will be searched for in the code directory", required=False)
    parser.add_argument("-d", "--start", help="Start date for processing in format YYYY-MM-DD (optional)", type=str, required=False, default="2000-01-01")
    parser.add_argument("-e", "--end", help="Start date for processing in format YYYY-MM-DD (optional)", type=str, required=False, default="3000-01-01")
    parser.add_argument("-v", "--verbose", help="Will provide debug logs. Default is false", type=str, default="false")
    parser.add_argument("--overwrite", help="Will Overwrite existing L2A products. Default is false", type=str, default="false")
    parser.add_argument("--nbackward", help="Number of products (if available) used to run in backward mode. Default is 8.", type=int, default=int(8))

    args = parser.parse_args()
    
    s = StartMaja(args.input, args.gipp, args.tile, args.site, args.folder, args.dtm, args.start, args.end, args.overwrite, args.nbackward, args.verbose)
    s.run()