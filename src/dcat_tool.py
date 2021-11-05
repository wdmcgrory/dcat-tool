#!/usr/bin/env python3
"""
List datasets and other information

"""

import os
import os.path
from os.path import abspath, dirname
import sys
import pprint
import glob
import time
import json

import openpyxl
import rdflib
from rdflib import Dataset, Graph, URIRef, Literal, Namespace, BNode

import template_reader
import dhs_ontology
import easy_workbook

INSTRUCTIONS  = os.path.join(dirname(abspath( __file__ )) , "instructions.md")

def make_template(fname, include_instructions, schemata_dir=dhs_ontology.SCHEMATA_DIR, schema_file=dhs_ontology.COLLECT_TTL, debug=False):
    v = dhs_ontology.Validator(schemata_dir, schema_file)
    eg = easy_workbook.ExcelGenerator()
    if include_instructions:
        eg.add_markdown_sheet("Instructions", open(INSTRUCTIONS).read())
    eg.add_columns_sheet("Inventory", v.ci_objs)
    eg.save( fname )

def read_xlsx(fname) :
    tr = template_reader.TemplateReader( fname )
    return list(tr.inventory_records())

def validate_inventory_records( records ):
    ret = {}
    ret['response'] = 200       # looks good
    ret['records']  = []
    ret['messages'] = []
    ret['errors']   = []
    v = dhs_ontology.Validator( args.schemata_dir, args.schema_file )
    for (num,record) in enumerate(records):
        ret['records'].append(record)
        try:
            v.add_row( record )
            ret['messages'].append('OK')
        except dhs_ontology.ValidationFail as e:
            ret['response'] = 409
            ret['errors'].append(num)
            ret['messages'].append(str(e))
    return ret


if __name__=="__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Use a DCAT schema to produce capture instruments and APIs.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--schemata_dir",
                        help="specify the directory to read all the schemata. If the --schema file is in schemata_dir, it will only be read once.",
                        default=dhs_ontology.SCHEMATA_DIR)
    parser.add_argument("--schema_file",
                        help="specify the collection schema file in Turtle, RDF/XML or RDF/JSON",
                        default=dhs_ontology.COLLECT_TTL)
    parser.add_argument("--debug", help="Enable debugging", action='store_true')
    parser.add_argument("--dumpts", help="Dump the triple store after everything it is read", action='store_true')
    parser.add_argument("--dumpci", help="Dump the collection instrument after everything it is read", action='store_true')
    parser.add_argument("--writeschema", help="write the schema to the specified file")
    parser.add_argument("--make_template",
                        help="specify the output filename of the Excel template to make for a collection schema")
    parser.add_argument("--read_xlsx", help="Read a filled-out Excel template and generate multi-line output JSON for each")
    parser.add_argument("--noinstructions", help="Do not generate instructions. Mostly for debugging.",
                        action='store_true')
    parser.add_argument("--validate_xlsx", help="Validate a filled-out Excel template and generate validateion report")
    parser.add_argument("--validate", help="Read a single JSON object on stdin and validate.", action='store_true')
    parser.add_argument("--validate_lines", help="Read multiple JSON objects on stdin and validate all.",
                        action='store_true')
    parser.add_argument("--convertJSON", help="Read simplified JSON on stdin line-by-line and output full RDF/JSON using DCATv3 spec",action='store_true')
    args = parser.parse_args()

    if args.dumpts:
        print("Dumping triple store:\n")
        for stmt in sorted( dhs_ontology.dcatv3_ontology(args.schemata_dir, args.schema_file) ):
            pprint.pprint(stmt)
            print()

    if args.dumpci:
        print("Dumping collection instrument:\n")
        v = dhs_ontology.Validator(schemata_dir = args.schemata_dir, schema_file=args.schema_file, debug=args.debug)
        for (ct,obj) in enumerate(v.ci_objs):
            print(ct,str(obj).replace("\n"," "))


    if args.validate:
        v = dhs_ontology.Validator( args.schemata_dir, args.schema_file )
        data = sys.stdin.readline()
        try:
            jin  = json.loads( data )
        except json.decoder.JSONDecodeError as e:
            print(e)
            print("offending input: ",data)
        try:
            v.validate( jin )
            print("OK")
        except dhs_ontology.ValidationFail as e:
            print("FAIL:"+e.message)

    if args.validate_lines:
        """Read lines of JSON, turn each one into a dictionary, then validate them all"""
        records = []
        fail = []
        line = 0
        while True:
            data = sys.stdin.readline()
            if len(data) == 0:
                break
            line += 1
            try:
                records.append( json.loads( data ) )
            except json.decoder.JSONDecodeError as e:
                fail.append([line, e.message])
                continue
        ret = validate_inventory_records(records)
        if ret['response']==200 and fail==[]:
            print("OK")
        else:
            print("FAILURE:")
            print(json.dumps(ret,indent=4))
            exit(1)

    if args.make_template:
        make_template(args.make_template, not args.noinstructions, schemata_dir=args.schemata_dir, schema_file=args.schema_file, debug=args.debug)

    if args.read_xlsx:
        for r in read_xlsx(args.read_xlsx):
            print( json.dumps(r) )

    if args.validate_xlsx:
        print(json.dumps(validate_inventory_records(read_xlsx(args.validate_xlsx)), indent=4))

    if args.writeschema:
        v = dhs_ontology.Validator( args.schemata_dir, args.schema_file )
        fmt = os.path.splitext(args.writeschema)[1][1:].lower()
        if fmt=='json':
            fmt='json-ld'
        v.g2.serialize(destination=args.writeschema, format=fmt)

    """
    This code is not working propertly.

Test:
echo '{ "dct:identifier": "id102", "dct:title": "This is ID102", "dct:description": "This is the third dataset" }' |  python dcat_tool.py --convertJSON

URLs for help:
https://github.com/RDFLib/rdflib/issues/543
https://stackoverflow.com/questions/65818401/namespace-binding-in-rdflib
https://www.programcreek.com/python/example/18799/rdflib.Namespace
https://stackoverflow.com/questions/28503628/force-rdflib-to-define-a-namespace
https://rdflib.readthedocs.io/en/4.0/_modules/rdflib/namespace.html
https://rdflib.readthedocs.io/en/stable/_modules/rdflib/namespace.html
https://github.com/RDFLib/rdflib/issues/1232
    """

    if args.convertJSON:
        v = dhs_ontology.Validator( args.schemata_dir, args.schema_file )
        g2 = v.cleanGraph()
        while True:
            data = sys.stdin.readline()
            if len(data) == 0:
                break
            obj = json.loads( data )
            bnode = BNode()     # a GUID is generated
            for (k,v) in obj.items():
                g2.add( ( bnode, URIRef(k), Literal(v)) )
            print(g2)
            print(g2.serialize( format='turtle'))
