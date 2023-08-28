from xml.sax.saxutils import escape
from doc_utils.metadata import parse_metadata, MetaData, Directive, TextBlock
from markdown import markdown
from collections import OrderedDict
from functools import partial
import doc_utils.api_tools as api_tools
import doc_utils.doc_tools as doc_tools
import os


gen_online_doc = False


def convert_markdown(text):
	md = markdown(text, extensions=['markdown.extensions.extra', 'markdown.extensions.codehilite', 'toc'])
	return '<div class="doc-details">\n<div class="doc-details-content">\n' + md + '</div>\n</div>\n'


def get_thesaurus(letters):
	letter_links = ' - '.join(
		[
			f'<a href="#thesaurus-{letter}">{letter.upper()}</a>'
			for letter in letters
		]
	)
	html = f'<p style="width: 100%; text-align: center;">{letter_links}'
	html += '</p>\n'

	return html


def gen_class_index(uid, link_formatter):
	class_uid = doc_tools.get_all_classes()

	letters = 'abcdefghijklmnopqrstuvwxyz'

	# classes by letter
	def uid_startswith(uid, l):
		if uid.startswith('man.'):
			uid = uid[4:]
		elif uid.startswith('gen.'):
			uid = uid[4:]
		return uid[:1].lower() == l

	classes_by_letter = {}
	for l in letters:
		classes_by_letter[l] = [uid for uid in class_uid if uid_startswith(uid, l)]

	# build a list of letters with elements
	letters = [l for l in letters if len(classes_by_letter[l]) > 0]

	# output thesaurus
	body = get_thesaurus(letters)

	# output index
	body += '<table class="table" markdown=1>\n'  # allow markdown parsing of the table links
	for i in range(0, len(letters), 4):
		row_count = 0
		for l in letters[i:i+4]:
			if len(classes_by_letter[l]) > row_count:
				row_count = len(classes_by_letter[l])

		if row_count > 0:
			body += '<tr>'
			for l in letters[i:i+4]:
				body += f'<th id="thesaurus-{l}">{l.upper()}</th>'
			body += '</tr>\n'

			for row in range(row_count):
				body += "<tr>\n"
				for l in letters[i:i+4]:
					if row < len(classes_by_letter[l]):
						body += '<td>[%s]</td>\n' % classes_by_letter[l][row]
					else:
						body += '<td></td>\n'
				body += "</tr>\n"

	body += "</table>\n"
	return body


def gen_tutorial_index(uid, link_formatter):
	# parse all tutorial tags
	tutorials_group = {}

	for uid, content in doc_tools.man.items():
		tutorial_directive_start = content.find(".tutorial")
		if tutorial_directive_start == -1:
			continue  # page is not a tutorial

		tutorial_directive_end = content.find(")", tutorial_directive_start)
		if tutorial_directive_end == -1:
			continue  # page is not a tutorial

		tutorial_directive = parse_metadata(content[tutorial_directive_start:tutorial_directive_end+1])
		parse_out = parse_tutorial_directive(tutorial_directive[0])

		if parse_out is None:
			print(f"Failed to parse .tutorial directive in {uid}")
			continue

		group = parse_out['group']
		if group not in tutorials_group:
			tutorials_group[group] = {}

		tutorials_group[group][uid] = parse_out

	# output index
	body = ''
	for group, tutorials in tutorials_group.items():
		body += f'### {group}' + '\n'
		body += '<table class="table" markdown=1>\n'  # allow markdown parsing of the table links
		body += '<col width="180">\n'

		body += '<tr><th>Title</th><th>Goal</th><th>Level</th><th>Duration</th><th>Language</th></tr>\n'
		for uid, parse_out in tutorials.items():
			body += '<tr>'
			body += f"<td>[{uid}]</td><td>{parse_out['goal']}</td><td>{parse_out['level']}</td><td>{parse_out['duration']} min</td><td>{parse_out['lang']}</td>"
			body += '</tr>\n'

		body += "</table>\n"

	return body


def is_class_abstract(uid):
	class_tag = api_tools.api[uid][0]  # class tag (should be)
	if class_tag.tag != "class":
		return False
	return class_tag.get("base_type", "0") == "1"


def gen_class_info(uid, link_formatter):
	inheritance = doc_tools.build_class_inheritance()
	related_classes, related_functions = gather_uids_related_to(uid)

	is_abstract = is_class_abstract(uid)

	inherits = [f'[{i}]' for i in inheritance[uid]]
	inherited_by = [f'[{nu}]' for nu, nh in inheritance.items() if uid in nh]
	related_to = [f'[{c}]' for c in related_classes]

	body = '<table class="table class-member-index" markdown=1>\n'

	if inherits:
		body += '<tr>'
		body += '<td style="width: 10%">Inherits:</td>'
		body += '<td>' + doc_tools.list_to_natural_string(sorted(inherits), "and") + '</td>'
		body += '</tr>\n'
	if inherited_by:
		body += '<tr>'
		body += '<td style="width: 10%">Inherited by:</td>'
		body += '<td>' + doc_tools.list_to_natural_string(sorted(inherited_by), "and") + '</td>'
		body += '</tr>\n'
	if len(related_classes) > 0:
		body += '<tr>'
		body += '<td style="width: 10%">Used by:</td>'
		body += '<td>' + doc_tools.list_to_natural_string(sorted(related_to), "and") + '</td>'
		body += '</tr>\n'

	if is_abstract:
		body += '<tr>'
		body += '<td colspan="2">This base type cannot be instantiated directly.</td>'
		body += '</tr>'

	body += '</table>\n'
	return body


def output_functions_index(funcs, href_prefix=""):
	body = '<table class="table class-member-index" markdown=1>\n'

	for fn_uid, tags in sorted(funcs.items()):
		body += '<tr>'
		rvalues, protos = [], []

		if fn_uid in api_tools.blacklist:
			continue

		for fn_tag in tags:
			rvalues.append(doc_tools.format_function_proto_rvalue(fn_tag))
			proto_parms = doc_tools.format_function_proto_parms(fn_tag)

			if fn_uid in doc_tools.doc:
				protos.append(
					f"""<strong><a href="{href_prefix}#{fn_uid}">{fn_tag.get('name')}</a></strong>{proto_parms}"""
				)
			else:
				protos.append(f"<strong>{fn_tag.get('name')}</strong>{proto_parms}")

		body += f"""<td class="text-right col-md-3">{'<br>'.join(rvalues)}</td>"""
		body += f"<td>{'<br>'.join(protos)}</td>"
		body += '</tr>\n'

	body += '</table>\n'
	return body


def gen_class_content_index(uid, link_formatter):
	member_functions, static_member_functions = OrderedDict(), OrderedDict()

	class_tag = api_tools.api[uid][0]  # there is only one class for a given uid

	body = str()

	if enum_tags := list(class_tag.iter('enum')):
		body += '## Enumerations ##\n'

		body += '<table class="table class-member-index" markdown=1>\n'
		for enum_tag in enum_tags:
			body += '<tr>'
			enum_uid = enum_tag.get('uid')
			name = enum_tag.get('name')
			entries = [f"**{tag.get('name')}**" for tag in enum_tag.iter('entry')]
			body += f'<td class="text-right col-md-3" style="vertical-align: text-top;" id="{enum_uid}">{name}</td>'

			body += '<td>'
			body += doc_tools.list_to_natural_string(entries, "or")
			body += '</td>'

			body += '</tr>\n'

		body += '</table>\n'

	if var_tags := list(class_tag.iter('variable')):
		body += '## Variables ##\n'

		body += '<table class="table class-member-index" markdown=1>\n'
		for var_tag in var_tags:
			body += '<tr>'
			type = doc_tools.format_uid_link(var_tag.get('type'))
			if var_tag.get("static") == "1":
				type = f"static {type}"
			body += f'<td class="text-right col-md-3" style="vertical-align: text-top;">{type}</td>'
			body += f"<td>{var_tag.get('name')}</td>"
			body += '</tr>\n'

		body += '</table>\n'

	# gather all class function tags
	for fn_tag in class_tag.iter('function'):
		fn_uid = fn_tag.get('uid')
		if fn_tag.get('static') == '1':
			static_member_functions[fn_uid] = static_member_functions.get(fn_uid, []) + [fn_tag]
		else:
			member_functions[fn_uid] = member_functions.get(fn_uid, []) + [fn_tag]

	#
	related_classes, related_functions = gather_uids_related_to(uid)

	if len(member_functions) > 0:
		body += '## Member Functions ##\n'
		body += output_functions_index(member_functions)
	if len(static_member_functions) > 0:
		body += '## Static Member Functions ##\n'
		body += output_functions_index(static_member_functions)
	if len(related_functions) > 0:
		body += '## Related Functions ##\n'
		body += output_functions_index(related_functions, "man.Functions.html")
	return body


def output_function_documentation(uid, tags, link_formatter):
	body = f'<div class="function_div" id="{uid}" markdown=1>'

	# output all prototypes
	protos = []
	for fn_tag in tags:
		rvalue = doc_tools.format_function_proto_rvalue(fn_tag)
		proto_parms = doc_tools.format_function_proto_parms(fn_tag)
		protos.append(f"{rvalue} <strong>{fn_tag.get('name')}</strong>{proto_parms}")

	body += f"""<div class="function_proto">{'<br>'.join(protos)}</div>"""

	# output function documentation
	body += '<div class="function_doc">'
	if uid in doc_tools.doc:
		body += doc_tools.doc[uid]
		body += '\n'  # prevent last markdown tag from being corrupted
	body += '</div>'

	body += '</div>'
	return body


def output_functions_documentation(funcs, link_formatter):
	body = str()
	for fn_uid, tags in sorted(funcs.items()):
		body += output_function_documentation(fn_uid, tags, link_formatter)
	return body


def gen_class_content_documentation(uid, link_formatter):
	member_functions_, static_member_functions_ = OrderedDict(), OrderedDict()

	class_tag = api_tools.api[uid][0]  # there is only one class for a given uid

	# gather all class function tags
	for fn_tag in class_tag.iter('function'):
		fn_uid = fn_tag.get('uid')
		if fn_tag.get('static') == '1':
			static_member_functions_[fn_uid] = static_member_functions_.get(fn_uid, []) + [fn_tag]
		else:
			member_functions_[fn_uid] = member_functions_.get(fn_uid, []) + [fn_tag]

	related_classes, related_functions_ = gather_uids_related_to(uid)

	# remove undocumented uids
	member_functions, static_member_functions, related_functions = OrderedDict(), OrderedDict(), {}

	for uid, tags in member_functions_.items():
		if uid in doc_tools.doc:
			member_functions[uid] = tags

	for uid, tags in static_member_functions_.items():
		if uid in doc_tools.doc:
			static_member_functions[uid] = tags

	for uid, tags in related_functions_.items():
		if uid in doc_tools.doc:
			related_functions[uid] = tags

	# output documentation
	body = str()
	if len(member_functions) > 0:
		body += "## Member Function Documentation ##\n"
		body += output_functions_documentation(member_functions, link_formatter)
		body += "\n"
	if len(static_member_functions) > 0:
		body += "## Static Member Function Documentation ##\n"
		body += output_functions_documentation(static_member_functions, link_formatter)
		body += "\n"
	return body


def output_enum_documentation(uid):
	enum_tag = api_tools.api[uid][0]

	body = "### %s ###\n" % uid
	for entry in list(enum_tag):
		name, value = entry.get("name"), entry.get("value")

		if name:
			body += f"- {name}"
			if value:
				body += f" = `{value}`"
			body += "\n"

	related_classes, related_functions = gather_uids_related_to(uid)
	related_to = [f'[{fn}]' for fn in related_functions] + [
		f'[{fn}]' for fn in related_classes
	]

	if len(related_to) > 0:
		body += "\n\nUsed by " + doc_tools.list_to_natural_string(sorted(related_to), "and") + "."

	return body


def output_constant_documentation(uid):
	constant_tag = api_tools.api[uid][0]

	body = "### %s ###\n" % uid
	for entry in list(constant_tag):
		if name := entry.get("name"):
			body += f"- {name}"
			body += "\n"

	related_classes, related_functions = gather_uids_related_to(uid)
	related_to = [f'[{fn}]' for fn in related_functions] + [
		f'[{fn}]' for fn in related_classes
	]

	if len(related_to) > 0:
		body += "\n\nUsed by " + doc_tools.list_to_natural_string(sorted(related_to), "and") + "."

	return body


def gen_enum_content(uid, link_formatter):
	related_classes, related_functions = gather_uids_related_to(uid)

	related_to = [f'[{c}]' for c in related_classes]

	body = '<table class="table class-member-index" markdown=1>\n'
	if related_to:
		body += '<tr>'
		body += '<td>Used by:</td>'
		body += '<td>' + doc_tools.list_to_natural_string(sorted(related_to), "and") + '</td>'
		body += '</tr>\n'
	body += '</table>\n'

	body += output_enum_documentation(uid)

	if len(related_functions) > 0:
		body += '## Related Functions ##\n'
		body += output_functions_index(related_functions)

	return body


def is_function_using_uid(fn_tag, uid):
	if fn_tag.get("returns") == uid:
		return True
	for parm in fn_tag:
		if parm.tag == "parm":
			if parm.get("type") == uid or parm.get("constants_group") == uid:
				return True
	return False


def is_class_using_uid(class_tag, uid):
	return any(
		fn_tag.tag == "function" and is_function_using_uid(fn_tag, uid)
		for fn_tag in class_tag
	)


related_to_cache = {}


def gather_uids_related_to(uid):
	if uid in related_to_cache:
		return related_to_cache[uid]

	classes, functions = [], {}

	for related_uid, tags in api_tools.api.items():
		if related_uid == uid:
			continue

		for tag in tags:
			if tag.tag == "function":  # look if a global function is using this uid
				if tag.get("global") == "1" and is_function_using_uid(tag, uid):
					functions[related_uid] = functions.get(related_uid, []) + [tag]
			elif tag.tag == "class":  # look if class has a function using this enum
				if is_class_using_uid(tag, uid):
					classes.append(related_uid)

	related_to_cache[uid] = (classes, functions)
	return classes, functions


def uids_to_link(uids):
	return [f'[{uid}]' for uid in uids]


def get_tag_uids(tag_name, globals_only = False):
	uids = []
	for uid_, tags in api_tools.api.items():
		if tags[0].tag == tag_name:
			if globals_only is False or tags[0].get("global") == "1":
				uids.append(uid_)
	return uids


def group_uids_per_category(tag_name, globals_only=False):
	cat_uids = {}
	for uid_, tags in api_tools.api.items():
		if tags[0].tag == tag_name:
			if globals_only is False or tags[0].get("global") == "1":
				cat = tags[0].get("name")[:1].upper()
				if not cat.isalpha():
					cat = "_"

				cat_uids[cat] = cat_uids.get(cat, []) + [uid_]

	return cat_uids


def uid_name(uid):
	return api_tools.api[uid][0].get("name")


#
def gen_index(category, globals_only, link_formatter, col_count, sub_col_count):
	cat_uids = group_uids_per_category(category, globals_only)

	letters = ''.join(cat.lower() for cat, uids in sorted(cat_uids.items()))
	# output categories content
	body = get_thesaurus(letters)
	body += '<table class="table index" markdown=1>\n'

	i = iter(sorted(cat_uids.items()))
	done = False

	while not done:
		body += '<tr>'

		for _ in range(col_count):
			try:
				cat, uids = next(i)

				if len(uids) == 0:
					continue

				body += '<td class="text-right" valign="top"><span class="category-name" id="thesaurus-%s">%s</span></td>\n' % (cat.lower(), cat)

				#
				body += '<td valign="top">\n'

				uids = sorted(uids, key=uid_name)

				sub_col_row_count = (len(uids) + sub_col_count - 1) // sub_col_count
				sub_col_size = 0

				for uid in uids:
					if sub_col_size == 0:
						body += '<div style="float: left; width: %.2f%%;">' % (100 / sub_col_count)

					body += f'[{uid}]'

					parent_tag = api_tools.api_parent_map[api_tools.api[uid][0]]
					parent_name = parent_tag.get("name")
					if parent_name is not None:
						body += f' ({parent_name})'

					body += '<br>'

					sub_col_size = sub_col_size + 1
					if sub_col_size == sub_col_row_count:
						body += '</div>\n'
						sub_col_size = 0

				if sub_col_size != 0:
					body += '</div>\n'

				body += '</td>'
			except StopIteration:
				done = True

		body += '</tr>'

	body += '</table>\n'
	return body


def gen_enum_index(globals_only, _, link_formatter):
	return gen_index('enum', globals_only, link_formatter, 3, 1)


def gen_function_index(globals_only, _, link_formatter):
	return gen_index('function', globals_only, link_formatter, 1, 2)


def gen_constants_index(globals_only, _, link_formatter):
	return gen_index('constants', globals_only, link_formatter, 3, 1)


#
def gen_function_documentation(uid, link_formatter):
	cat_uids = group_uids_per_category("function", True)

	body = str()
	for cat, uids in sorted(cat_uids.items()):
		if uids_tags := {uid: api_tools.api[uid] for uid in uids}:
			body += "## %s ##\n" % cat
			body += output_functions_documentation(uids_tags, link_formatter)
			body += "\n"

	return body


def gen_enum_documentation(uid, link_formatter):
	cat_uids = group_uids_per_category("enum", True)

	body = str()
	for cat, uids in sorted(cat_uids.items()):
		if uids_tags := {uid: api_tools.api[uid] for uid in uids}:
			body += "## %s ##\n" % cat
			for uid_ in uids_tags:
				body += "<div id=%s markdown=1>\n" % uid_
				body += output_enum_documentation(uid_)
				body += "\n</div>\n"

	return body


def gen_constants_documentation(uid, link_formatter):
	cat_uids = group_uids_per_category("constants", True)

	body = str()
	for cat, uids in sorted(cat_uids.items()):
		if uids_tags := {uid: api_tools.api[uid] for uid in uids}:
			body += "## %s ##\n" % cat
			for uid_ in uids_tags:
				body += "<div id=%s markdown=1>\n" % uid_
				body += output_constant_documentation(uid_)
				body += "\n</div>\n"

	return body


generated_symbols = {
	'%ClassIndex%': gen_class_index,
	'%GlobalFunctionIndex%': partial(gen_function_index, True),
	'%GlobalFunctionDocumentation%': gen_function_documentation,
	'%GlobalEnumIndex%': partial(gen_enum_index, True),
	'%GlobalEnumDocumentation%': gen_enum_documentation,
	'%GlobalConstantsIndex%': partial(gen_constants_index, True),
	'%GlobalConstantsDocumentation%': gen_constants_documentation,
	'%AllFunctionIndex%': partial(gen_function_index, False),
	'%AllEnumIndex%': partial(gen_enum_index, False),
	'%ClassInfo%': gen_class_info,
	'%ClassContentIndex%': gen_class_content_index,
	'%ClassContentDocumentation%': gen_class_content_documentation,
	'%EnumConstant%': gen_enum_content,
	'%TutorialIndex%': gen_tutorial_index,
}


def default_link_target_formatter(uid, is_img_link=False):
	# link to a manual page
	if uid in doc_tools.man:
		return f"[{doc_tools.get_element_title(uid)}]({uid})"

	# link to an API symbol
	if uid in api_tools.api:
		tag = api_tools.api[uid][0]
		parent = api_tools.api_parent_map[tag]

		if parent.tag == "class":  # symbol is a class
			parent_uid = parent.get("uid")
			return f"""<a href='{parent_uid}.html#{uid}'>{tag.get("name")}</a>"""

	# generic link
	return f"<a href='{uid}'>{uid}</a>"


def title_directive_to_text(o, link_formatter):
	return ""


def section_directive_to_text(o, link_formatter):
	def get_parm(o_, name_):
		return o_.parms[name_].value[1:-1]

	html = '<div class="doc-section">\n'

	name, icon = get_parm(o, "name"), get_parm(o, "icon")
	html += '<h2>%s</h2>\n' % name

	html += '<table width="100%">\n'
	html += '<tbody>\n'

	for r in o.content:
		if r.name != 'row':
			continue

		i = 0
		in_tr = False

		for b in r.content:
			if b.name != 'block':
				continue

			if not in_tr:
				html += '<tr style="vertical-align: top; min-height: 128px;">\n'
				in_tr = True

			html += '<td width="33%">\n'
			html += f"""<p><a href="{get_parm(b, 'link')}.html">{get_parm(b, 'name')}</a></p>"""
			if gen_online_doc:
				html += f"<p>{get_parm(b, 'desc')}</p>"
			else:
				html += f"<p><small>{get_parm(b, 'desc')}</small></p>"
			html += '</td>\n'

			i += 1
			if i == 3:  # close row
				html += '</tr>\n'
				in_tr = False
				i = 0

	html += '</tbody>\n'
	html += '</table>\n'
	html += '</div>\n'

	return html


def img_to_text(o, link_formatter):
	return '<img src="%s"><br>\n' % link_formatter(o.parm, True)


def parse_tutorial_directive(o):
	try:
		for key, value in o.parms.items():
			if key == 'duration':
				duration = value.value
			elif key == 'goal':
				goal = value.value.strip('"')
			elif key == 'group':
				group = str(value.value).strip('"')

			elif key == 'lang':
				lang = str(value.value)
			elif key == 'level':
				level = value.value.strip('"')
		return {'goal': goal, 'level': level, 'duration': duration, 'lang': lang, 'group': group}
	except:
		return None


def tutorial_to_text(o, link_formatter):
	parse_out = parse_tutorial_directive(o)
	if parse_out is None:
		return "<corrupt .tutorial directive>"

	html = '<table class="tutorial-header">'
	html += f"<tr><td>Goal:</td><td>{parse_out['goal']}</td></tr>"
	html += f"<tr><td>Difficulty:</td><td>{parse_out['level']}</td></tr>"
	html += f"<tr><td>Duration:</td><td>{parse_out['duration']} minutes</td></tr>"
	html += f"<tr><td>Language:</td><td>{parse_out['lang']}</td></tr>"
	html += '</table>\n'
	return html


directive_to_text = {
	'title': title_directive_to_text,
	'section': section_directive_to_text,
	'img': img_to_text,
	'tutorial': tutorial_to_text,
}


def metadata_object_to_text(o, link_formatter):
	if isinstance(o, MetaData):
		return "".join(metadata_object_to_text(s, link_formatter) for s in o)
	elif isinstance(o, Directive):
		if o.name in directive_to_text:
			return directive_to_text[o.name](o, link_formatter)
		return "** No handler for directive of type '%s' **\n" % o.name
	elif isinstance(o, TextBlock):
		return o.content  # content is raw string


def resolve_internal_links(this_uid, text, link_formatter, explicit_link_only=True, indirect=False):
	"""Replace all API UIDs with link to the documentation"""

	# uid documentation aliasing (quote documentation from an uid)
	if api_tools.api is not None:
		for uid, value in api_tools.api.items():
			link_decl = f"[{uid}:doc]"
			if text.find(link_decl) == -1:
				continue
			data = doc_tools.get_content_always(uid)
			text = text.replace(link_decl, format_page_content(uid, data, default_link_target_formatter, True))

	# uid link (for aliased documentation)
	if not indirect:
		text = text.replace('[:uid]', this_uid)

	# ------------------------------------------------------------------------
	def get_link_decl(uid):
		return f"[{uid}]" if explicit_link_only else uid

	# link to api pages
	if api_tools.api is not None:
		for uid, value in api_tools.api.items():
			link_decl = get_link_decl(uid)
			if text.find(link_decl) == -1:
				continue
			text = text.replace(link_decl, link_formatter(uid))

	# link to manual pages
	for uid, value in doc_tools.man.items():
		text = text.replace(get_link_decl(uid), link_formatter(uid))

	return text


def resolve_imports(text):
	"""Replace import directives"""
	pos = 0
	while True:
		pos = text.find("[import:", pos)
		if pos == -1:
			break

		end = text.find("]", pos)
		if end == -1:
			break  # mangled directive

		# parse the import directive
		args = text[pos + 8: end].split(',')
		filename = args[0]

		import_content = ""
		try:
			with open(args[0], 'r') as file:
				import_content = ''.join(file.readlines())
		except:
			import_content = f"[Import directive failed to load file '{args[0]}' (cwd is {os.getcwd()})]"

		text = text[:pos] + import_content + text[end + 1:]
		pos = end + 1

	return text


def parse_symbol_parms(text, start):
	if text[start:start+1] != "(":
		return None, None, None  # no args

	end = text.find(")", start+1)
	if end == -1:
		print("Mangled args in symbol directive")
		return None, None, None  # mangled args

	args = [arg.strip() for arg in text[start+1:end].split(",")]
	return args, start, end + 1


def replace_generated_symbols(uid, text, link_formatter):
	"""Replace all generated symbols with their content"""
	for sym, gen in generated_symbols.items():
		while True:
			# look for a symbol match
			sym_pos = text.find(sym)
			if sym_pos == -1:
				break  # no more match

			# grab optional symbol arguments
			args, args_start, args_end = parse_symbol_parms(text, sym_pos + len(sym))

			# evaluate symbol
			gen_uid = uid
			if args is not None and len(args) == 1:
				if args[0] in api_tools.api:
					gen_uid = args[0]

			output = gen(gen_uid, link_formatter)

			# and perform replace
			sym_end = args_end if args is not None else sym_pos + len(sym)
			text = text[:sym_pos] + output + text[sym_end:]

	return text


def format_text(uid, text, link_formatter, indirect):
	text = replace_generated_symbols(uid, text, link_formatter)
	text = resolve_internal_links(uid, text, link_formatter, True, indirect)
	text = resolve_imports(text)
	return convert_markdown(text)  # convert from markdown to HTML


def format_page_content(uid, data, link_formatter=default_link_target_formatter, indirect=False):
	"""Format the page content string to HTML"""
	data = parse_metadata(data)

	# parse all objects to build the final markdown text
	text = metadata_object_to_text(data, link_formatter)
	return format_text(uid, text, link_formatter, indirect)


def format_html_link(uid):
	"""Format a link across the documentation from an element UID"""
	return f"{uid}.html"


def get_language_switcher_js():
	return\
		'<script language="javascript" type="text/javascript">\n'\
		'function findCSSRule(selector) {\n'\
		'	var mySheet = document.styleSheets[0];\n'\
		'	var ruleIndex = -1;\n'\
		'	var theRules = mySheet.cssRules ? mySheet.cssRules : mySheet.rules;\n'\
		'	for (i=0; i<theRules.length; i++) {\n'\
		'		if (theRules[i].selectorText == selector) {\n'\
		'			ruleIndex = i;\n'\
		'			break;\n'\
		'		}\n'\
		'	}\n'\
		'	return ruleIndex;\n'\
		'}\n'\
		'function changeRule(selector, property, setting) {\n'\
		'	var mySheet = document.styleSheets[0];\n'\
		'	var theRule = mySheet.cssRules ? mySheet.cssRules[findCSSRule(selector)] : mySheet.rules[findCSSRule(selector)];\n'\
		'	eval(\'theRule.style.\' + property + \'="\' + setting + \'"\');\n'\
		'	return false;\n'\
		'}\n'\
		'</script>\n'


def get_language_switcher_div():
	return\
		'<div class="lang_switch">\n'\
		'<a href="#" onclick="changeRule(\'.python\', \'display\', \'inline\'); changeRule(\'.lua\', \'display\', \'none\'); return false;">Python</a>\n'\
		'<a href="#" onclick="changeRule(\'.python\', \'display\', \'none\'); changeRule(\'.lua\', \'display\', \'inline\'); return false;">Lua</a>\n'\
		'</div>\n'


def get_html_header():
	html = '<head>\n' + '<meta charset="utf-8">\n'
	html += '<link rel="stylesheet" href="doc.css">\n'
	html += get_language_switcher_js()
	html += '</head>\n'
	return html


def clean_visible_string(s):
	return escape(s)
