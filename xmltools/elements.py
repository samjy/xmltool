#!/usr/bin/env python

from lxml import etree
import utils


class SubElement(object):
    _attrs = []

    def __init__(self, text):
        self.name = text
        self.required = True
        self.islist = False
        self.conditional_names = []
        self.attrs = {}

        if text.endswith('+'):
            self.name = text[:-1]
            self.islist = True
        elif text.endswith('*'):
            self.name = text[:-1]
            self.islist = True
            self.required = False
        elif text.endswith('?'):
            self.name = text[:-1]
            self.required = False

        if '|' in self.name:
            text = self.name.replace('(', '').replace(')', '')
            conditional_names = text.split('|')
            for name in conditional_names:
                elt = type(self)(name)
                # If the conditional element is a list, the conditionals
                # are also a list
                # TODO: add test for islist
                elt.islist = self.islist
                self.conditional_names += [elt]

    def __repr__(self):
        return '<name=%(name)s required=%(required)s islist=%(islist)s>' % vars(self)


class TextElement(object):

    #: The XML tag name corresponding to this class
    name = None
    #: The object :class: `Generator` used to generate the classes
    _generator = None
    #: List of dtd attributes
    _attrs = []

    def __init__(self, value=None):
        self.value = value
        self.attrs = {}


class Element(object):
    """After reading a dtd file we construct some Element
    """
    #: The XML tag name corresponding to this class
    name = None
    #: The object :class: `Generator` used to generate the classess
    _generator = None
    #: List of dtd attributes
    _attrs = []
    #: List of :class:`SubElement`
    _elements = []

    def __init__(self):
        self.attrs = {}

    def _get_element(self, name):
        """Get SubElement corresponding to the given name

        :param name: the name to find
        :type name: str
        :return: The matching SubElement or None
        :rtype: SubElement
        """
        for elt in self._elements:
            names = [elt.name]
            if elt.conditional_names:
                names = [n.name for n in elt.conditional_names]
            for n in names:
                if n == name:
                    return elt
        return None

    def __getitem__(self, item):
        """Be able to get the property as a dict.

        :param item: the property name to get
        :type item: str
        :return: the value of the property named item
        :rtype: :class: `Element`, :class: `TextElement` or list
        """
        return getattr(self, item)

    def __setitem__(self, item, value):
        """Set the value for the given property item as a dict

        :param item: the property name to set
        :type item: str
        :param value: the value to set
        :type value; str
        """
        setattr(self, item, value)

    def __contains__(self, item):
        """Check item if defined

        :param item: the property name to check
        :type item: str
        :return: True of item is defined in self
        :rtype: bool
        """
        res = getattr(self, item, None)
        if res is None:
            return False
        return True

    def __setattr__(self, item, value):
        """Set the value for the given property item

        :param item: the property name to set
        :type item: str
        :param value: the value to set
        :type value: str
        """
        if item != 'attrs':
            elt = self._get_element(item)
            if not elt:
                raise Exception('Invalid child %s' % item)
            if elt.islist:
                cls = list
            else:
                cls = self._generator.dtd_classes.get(item)
            if not cls:
                raise Exception('Invalid child %s' % item)
            if value is not None and not isinstance(value, cls):
                raise Exception('Wrong type for %s' % item)
        super(Element, self).__setattr__(item, value)

    def create(self, tagname, text=None):
        """Create an element

        :param tagname: the tag name to create
        :type tagname: str
        :param text: if element is a :class: `TextElement` we set the value
        :type text: str
        :return: the create object
        :rtype: instance of TextElement or Element
        """
        if getattr(self, tagname, None) is not None:
            raise Exception('%s already defined' % tagname)

        if tagname not in self._generator.dtd_classes:
            raise Exception('Unexisting tagname %s' % tagname)

        cls = self._generator.dtd_classes[tagname]
        elt = self._get_element(tagname)
        if elt.islist:
            if elt.conditional_names:
                other_names = [n.name for n in elt.conditional_names if
                         n.name != tagname]
                for name in other_names:
                    if name in self:
                        raise Exception("You can't add a %s since it "
                                        "already contains a %s" % (
                                            tagname,
                                            name))
            obj = ElementList(cls)
        else:
            cls = self._generator.dtd_classes.get(tagname)
            if not cls:
                raise Exception('Invalid child %s' % tagname)
            obj = cls()

        if text:
            if isinstance(obj, TextElement):
                obj.value = text
            else:
                raise Exception("Can't set value to non TextElement")
        setattr(self, tagname, obj)
        return obj

    def to_xml(self):
        """Generate the XML string for this object

        :return: The XML as string
        :rtype: str
        """
        gen = self._generator
        xml = gen.obj_to_xml(self)

        return etree.tostring(
            xml.getroottree(),
            pretty_print=True)

    def write(self, xml_filename, encoding='UTF-8', validate_xml=True,
              transform=None):
        """Update the file named xml_filename with obj.

        :param xml_filename: the XML filename we should update
        :type xml_filename: str
        :param encoding: the encoding to use when writing the XML file.
        :type encoding: str
        :param validate_xml: validate the updated XML before writing it.
        :type validate_xml: bool
        :param transform: function to transform the XML string just before
            writing it.
        :type transform: function
        :return: self
        :rtype: :class:`Element`
        """
        gen = self._generator
        xml = gen.obj_to_xml(self)

        if validate_xml:
            dtd_str = utils.get_dtd_content(gen._dtd_url)
            utils.validate_xml(xml, dtd_str)

        doctype = ('<!DOCTYPE %(root_tag)s PUBLIC '
                   '"%(dtd_url)s" '
                   '"%(dtd_url)s">' % {
                       'root_tag': self.name,
                       'dtd_url': gen._dtd_url,
                   })

        xml_str = etree.tostring(
            xml.getroottree(),
            pretty_print=True,
            xml_declaration=True,
            encoding=encoding,
            doctype=doctype)
        if transform:
            xml_str = transform(xml_str)
        open(xml_filename, 'w').write(xml_str)


class ElementList(list):

    def __init__(self, cls):
        super(ElementList, self).__init__()
        self.cls = cls

    def add(self, text=None, position=None):
        """Add element in this list object

        :param text: if element is a :class: `TextElement` we set the value
        :type text: str
        :param position: the position in the list we want to insert the object
        :type position: int
        :rtype: instance of TextElement or Element
        """
        obj = self.cls()
        if text:
            if isinstance(obj, TextElement):
                obj.value = text
            else:
                raise Exception("Can't set value to non TextElement")
        if position is not None:
            self.insert(position, obj)
        else:
            self.append(obj)
        return obj

