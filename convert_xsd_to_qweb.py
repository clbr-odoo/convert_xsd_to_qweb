from lxml import etree
import json
import re

def camel_to_snake(camel_str):
    # Use regex to insert underscores before each capital letter (except the first one)
    if not isinstance(camel_str, str):
        return
    snake_str = re.sub('([a-z0-9])([A-Z])', r'\1_\2', camel_str)
    return snake_str.lower()


def pre_process_attrs(basic_components_file, unqualified_data_types_files):
    """Builds a set of Node name that should have a t-att attribute."""
    schema_cbc = etree.parse(basic_components_file)
    # schema_udt = etree.parse(unqualified_data_types_files)
    root_cbc = schema_cbc.getroot()
    # root_udt = schema_udt.getroot()
    attrs = set()
    type_to_element = {}
    for element in root_cbc:
        if element.tag == '{http://www.w3.org/2001/XMLSchema}element':
            name = element.attrib.get("name")
            eltype = element.attrib.get("type")
            type_to_element[eltype] = name
        elif element.tag == '{http://www.w3.org/2001/XMLSchema}complexType':
            name = element.attrib.get("name")
            if name in type_to_element:
                attrs.add(type_to_element[name])
    # TODO UDT for CII (facturx)
    return attrs


def xsd_to_qweb(xsd_file, qweb_file, set_cbc_attributes, json_file=None):

    def add_node_template(parent, name, element_type):
        template_node = etree.SubElement(parent, 'template', {'id': f"ubl_21_{name}"})
        etree.SubElement(template_node, 't', {'t-call': f"account_edi_ubl_cii.ubl_21_{element_type}"})

    def add_node_template_call(parent, element_type, foreach=False, ns='cac'):
        if foreach:
            t_node = etree.SubElement(parent, f'{{{namespaces[ns]}}}{element_type}', {
                't-foreach': f"vals.get('{camel_to_snake(element_type)}_list, [])",
                't-as': f"{camel_to_snake(element_type)}",
            })
            t_sub = etree.SubElement(t_node, 't', {'t-call': f"account_edi_ubl_cii.ubl_21_{element_type}"})
            etree.SubElement(t_sub, 't', {'t-set': 'vals', 't-value': camel_to_snake(element_type)})
            json_dict.update({f'{camel_to_snake(element_type)}_list': []})
        else:
            t_node = etree.SubElement(parent, f'{{{namespaces[ns]}}}{element_type}')
            t_sub = etree.SubElement(t_node, 't', {'t-call': f"account_edi_ubl_cii.ubl_21_{element_type}"})
            etree.SubElement(t_sub, 't', {'t-set': 'vals', 't-value': f"vals.get('{camel_to_snake(element_type)}', {{}}"})
            json_dict.update({f'{camel_to_snake(element_type)}': {}})

    def add_leaf(parent, element_type, ns='cbc'):
        json_dict.update({f'{camel_to_snake(element_type)}': None})
        attrib = {'t-out': f"vals.get('{camel_to_snake(element_type)}')"}
        if element_type in set_cbc_attributes:
            # json_dict.update({f'{camel_to_snake(element_type)}_attrs': {}})
            attrib.update({'t-att': f'{camel_to_snake(element_type)}_attrs'})
        etree.SubElement(parent, f'{{{namespaces[ns]}}}{element_type}', attrib)

    namespaces = {
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
    }

    # Parse the XSD file.
    schema = etree.parse(xsd_file)
    input_root = schema.getroot()
    json_dict = {}

    # Initialize QWEB template
    qweb_root = etree.Element('odoo')
    comment_1 = etree.Comment('Automatically generated from XSD file: https://docs.oasis-open.org/ubl/os-UBL-2.1/xsdrt/')
    comment_2 = etree.Comment('with script <TODO insert url>')
    qweb_root.append(comment_1)
    qweb_root.append(comment_2)

    # Iterate through the XSD elements
    for element in input_root:
        if element.tag == '{http://www.w3.org/2001/XMLSchema}element':
            name = element.attrib.get("name")
            eltype = element.attrib.get("type")
            add_node_template(qweb_root, name, eltype)

        if element.tag == '{http://www.w3.org/2001/XMLSchema}complexType':
            main_template = etree.SubElement(qweb_root, 'template', nsmap=namespaces)
            for child in element[0]:
                prefix, eltype = child.attrib.get("ref").split(':')
                multiplicity_max = child.attrib.get("maxOccurs")
                if prefix == "cbc":
                    if not main_template.attrib.get('id') and element.attrib.get("name"):
                        main_template.attrib['id'] = f'ubl_21_{element.attrib["name"]}'
                    add_leaf(main_template, eltype)
                elif prefix in ("cac", "ext"):
                    if multiplicity_max == 'unbounded':
                        add_node_template_call(main_template, eltype, foreach=True, ns=prefix)
                    else:
                        add_node_template_call(main_template, eltype, ns=prefix)
                else:
                    print(f'Unhandled prefix: {prefix}')


    # Write the QWEB template to the output file
    with open(qweb_file, 'w') as f:
        xml_str = etree.tostring(qweb_root, pretty_print=True, xml_declaration=True)
        formatted_xml = xml_str.decode('utf-8').replace('  ', '    ')  # Replacing 2 spaces with 4
        f.write(formatted_xml)
    if json_file:
        with open(json_file, 'w') as fjson:
            json.dump(json_dict, fjson, indent=4)


# Example usage
set_attrs = pre_process_attrs('resources/ubl/xsd/UBL-CommonBasicComponents-2.1.xsd', 'resources/ubl/xsd/UBL-UnqualifiedDataTypes-2.1.xsd')
xsd_to_qweb('resources/ubl/xsd/UBL-CommonAggregateComponents-2.1.xsd', './output/common_aggregate_components.xml', set_attrs, json_file='./output/cac.json')
xsd_to_qweb('resources/ubl/xsd/UBL-Invoice-2.1.xsd', './output/invoice.xml', set_attrs, json_file='./output/invoice.json')
xsd_to_qweb('resources/ubl/xsd/UBL-CreditNote-2.1.xsd', './output/credit_note.xml', set_attrs)
xsd_to_qweb('resources/ubl/xsd/UBL-DebitNote-2.1.xsd', './output/debit_note.xml', set_attrs)
xsd_to_qweb('resources/ubl/xsd/UBL-Order-2.1.xsd', './output/order.xml', set_attrs)
xsd_to_qweb('resources/ubl/xsd/UBL-ApplicationResponse-2.1.xsd', './output/application_response.xml', set_attrs)
