#!/usr/bin/env python3

import sys, os, re, math, copy
import json, hashlib, collections

shader_idx_filename = 'ShaderHeaders.json'

# Tokeniser loosely based on
# https://docs.python.org/3.4/library/re.html#writing-a-tokenizer

class Token(str): pass

class Strip(object): pass # Removed during tokenisation
class Ignore(object): pass # Ignored when looking for identifiers

class CPPStyleComment(Token, Strip):
    pattern = r'\/\/.*$'

def strip_quotes(s):
    if s[0] == s[-1] == '"':
        return s[1:-1].strip()
    return s.strip()

class String(Token):
    pattern = r'"[^"]*"'

class CurlyLeft(Token):
    pattern = r'{'

class CurlyRight(Token):
    pattern = r'}'

class WhiteSpace(Token, Ignore):
    pattern = r'[ \t]+'

class NewLine(WhiteSpace, Token):
    pattern = r'\n'

class Identifier(Token):
    pattern = r'[a-zA-Z0-9\[\]_]+'

class Other(Token):
    pattern = r'.'

tokens = [
    CPPStyleComment,
    String,
    CurlyLeft,
    CurlyRight,
    NewLine,
    WhiteSpace,
    Identifier,
    Other,
]

def tokenise(input):
    token_dict = {token.__name__: token for token in tokens}
    tok_regex = r'|'.join('(?P<%s>%s)' % (token.__name__, token.pattern) for token in tokens)
    for mo in re.finditer(tok_regex, input, re.MULTILINE):
        kind = token_dict[mo.lastgroup]
        value = kind(mo.group(mo.lastgroup))
        if not isinstance(value, Strip):
            yield value

def _curly_scope(old_tree, pos):
    tree = Tree()
    end = len(old_tree)
    while pos < end:
        token = old_tree[pos]
        if isinstance(token, CurlyRight):
            return (tree, pos)
        if isinstance(token, CurlyLeft):
            (branch, pos) = _curly_scope(old_tree, pos + 1)
            assert(pos is not None)
            tree.append(branch)
        else:
            tree.append(token)
        pos += 1
    return (tree, None)

def curly_scope(old_tree):
    (tree, pos) = _curly_scope(old_tree, 0)
    assert(pos is None)
    return tree

def ignore_whitespace(tree):
    for token in tree:
        if isinstance(token, Ignore):
            continue
        yield token

def next_interesting(tree):
    while True:
        r = next(tree)
        if isinstance(r, Ignore):
            continue
        return r

class Keyword(object):
    def __init__(self, keyword, tokens, parent, args):
        self.keyword = keyword
        self.parent = parent
        return self.parse(tokens, parent, args)

    def __str__(self):
        return self.keyword

def stringify(tree):
    # Needed because Tokens aren't subclassed from str. Tokens aren't
    # subclassed from str because doing so means we can't use __str__ to
    # transform "blah" into blah (Could probably fix this by transforming it in
    # __new__ instead, but I need to fix the tokeniser).
    return ''.join(map(str, tree))

def stringify_nl(tree):
    return '\n'.join(map(str, tree))

class Tree(list):
    def __str__(self):
        if len(self) == 0:
            return '{}'
        return '{%s}' % stringify(self)

class NamedTree(Keyword, Tree):
    def parse(self, tokens, parent, args):
        self.orig_name = next_interesting(tokens)
        self.name = strip_quotes(self.orig_name)
        Tree.__init__(self, parse_keywords(next_interesting(tokens), parent=self, args=args))

    def header(self):
        return '%s %s {' % (Keyword.__str__(self), self.orig_name)

    def __str__(self):
        return '%s\n%s\n}' % (self.header(), stringify_nl(self))

class UnnamedTree(Keyword, Tree):
    @property
    def parent_counter_attr(self):
        return '%s_counter' % self.keyword

    @property
    def parent_counter(self):
        return getattr(self.parent, self.parent_counter_attr, 0)

    @parent_counter.setter
    def parent_counter(self, val):
        return setattr(self.parent, self.parent_counter_attr, val)

    def parse(self, tokens, parent, args):
        self.parent_counter += 1
        self.counter = self.parent_counter

        Tree.__init__(self, parse_keywords(next_interesting(tokens), parent=self, args=args))

    def header(self):
        return '%s %i/%i {' % (Keyword.__str__(self), self.counter, self.parent_counter)

    def __str__(self):
        return '%s\n%s\n}' % (self.header(), stringify_nl(self))

class StringifyLine(Keyword):
    def parse(self, tokens, parent, args):
        t = []
        while True:
            token = next(tokens)
            if isinstance(token, NewLine):
                break
            t.append(token)
        self.line = stringify(t)

    def __str__(self):
        return '%s %s' % (Keyword.__str__(self), self.line.strip())

class Keywords(Keyword, set):
    def parse(self, tokens, parent, args):
        set.__init__(self, map(strip_quotes, map(str, ignore_whitespace(next_interesting(tokens)))))

    def __str__(self):
        kws = ['"%s"' % x for x in sorted(self)]
        return '%s { %s }' % (Keyword.__str__(self), ' '.join(kws))

# The syntax in this file format is very inconsistent, making it difficult to
# write a generic parser that handles everything properly unless it knows what
# type all the keywords are.
keywords = {
        'Shader': NamedTree,
        'Program': NamedTree,
        'SubProgram': NamedTree,

        'SubShader': UnnamedTree,
        'Pass': UnnamedTree,

        'Keywords': Keywords,

        # Anything else will be processed by StringifyLine
}

shader_index = {}
shader_list = []
hash_list = {}
hash_headers = {}

def handle_shader_asm(token, parent, asm):
    parent.shader_asm = asm
    # Index shaders by assembly:
    if token in shader_index:
        # Minimise calls to shaderasm.exe
        parent.hash = shader_index[token][0].hash
        parent.hash_type = shader_index[token][0].hash_type
        parent.hash_fmt = shader_index[token][0].hash_fmt
    else:
        shader_index[token] = []
        add_shader_hash(parent)
        if parent.hash:
            if parent.hash in hash_list:
                if parent.hash_type == 'crc32':
                    print('%s WARNING: CRC32 COLLISION DETECTED: %.8X %s' % ('-'*17, parent.hash, '-'*17))
                elif parent.hash_type == '3Dmigoto':
                    print('%s WARNING: 3DMigoto HASH COLLISION DETECTED: %.16x %s' % ('-'*17, parent.hash, '-'*17))
                else:
                    print('%s WARNING: HASH COLLISION DETECTED: %.16x %s' % ('-'*17, parent.hash, '-'*17))
                hash_list[parent.hash].append(parent)
                print('\n'.join([ \
                        os.path.sep.join(export_filename_combined_long([get_parents(x)], None)) \
                        for x in hash_list[parent.hash] ]))
                print('%s OVERRIDING THESE SHADERS MAY BE DANGEROUS %s' % ('-'*18, '-'*18))
                print()
            else:
                hash_list[parent.hash] = [parent]
    shader_index[token].append(parent)
    shader_list.append(parent)

def create_fog_asm(asm):
    tree = shadertool.parse_shader(asm)
    return shadertool.add_unity_autofog(tree)

def parse_keywords(tree, parent=None, filename=None, args=None):
    ret = []
    tokens = iter(tree)
    if parent is not None and not hasattr(parent, 'keywords'):
        parent.keywords = {}
    while True:
        try:
            token = next_interesting(tokens)
        except StopIteration:
            break

        if isinstance(token, String):
            parent.fog = None
            if args.type and parent.name not in args.type:
                continue
            handle_shader_asm(token, parent, strip_quotes(token))
            continue

        if not isinstance(token, Identifier):
            raise SyntaxError('Expected Identifier, found: %s' % repr(token))

        if token in keywords:
            item = keywords[token](token, tokens, parent, args)
        else:
            # I used to be strict and fail on any unrecognised keywords, but I
            # kept running into more so now I just stringify them:
            item = StringifyLine(token, tokens, parent, args)

        if filename is not None:
            item.filename = filename
        ret.append(item)

        if parent is not None:
            if token not in parent.keywords:
                parent.keywords[token] = []
            parent.keywords[token].append(item)

    return ret

def get_parents(sub_program):
    Shader = collections.namedtuple('Shader', ['sub_program', 'program', 'shader_pass', 'sub_shader', 'shader'])

    program = sub_program.parent
    shader_pass = program.parent
    sub_shader = shader_pass.parent
    shader = sub_shader.parent

    assert(sub_program.keyword == 'SubProgram')
    assert(program.keyword == 'Program')
    assert(shader_pass.keyword == 'Pass')
    assert(sub_shader.keyword == 'SubShader')
    assert(shader.keyword == 'Shader')

    return Shader(sub_program, program, shader_pass, sub_shader, shader)

abbreviations = (
    ('DIRECTIONAL', 'DIR'),
    ('COOKIE', 'CK'),
    ('POINT', 'PT'),
    ('SHADOWS', 'SHDW'),
    ('SOFT', 'SFT'),
    ('CUBE', 'CBE'),
    ('SCREEN', 'SCN'),
    ('NATIVE', 'NTV'),
    ('DEPTH', 'DEP'),
    ('OFF', 'OF'),
    ('SPOT', 'SPT'),
    ('SUNSHINE', 'SUN'),
    ('FILTER', 'FLT'),
    ('HARD', 'HRD'),
    ('SOFT', 'SFT'),
    ('DISABLED', 'DIS'),
)

def abbreviate(word):
    for a in abbreviations:
        word = word.replace(*a)
    return word


def compress_keywords(keywords):
    keywords = map(abbreviate, keywords)
    split = [x.rsplit('_', 1) for x in keywords]

    ret = []

    ret.extend([x[0] for x in split if len(x) == 1])
    multiword = [x for x in split if len(x) > 1]
    for word in set([x[0] for x in multiword]):
        remaining = [x[1] for x in multiword if x[0] == word]
        if len(remaining) == 1:
            ret.append('%s_%s' % (word, ''.join(remaining)))
        else:
            ret.append('%s_(%s)' % (word, '+'.join(remaining)))
    return ' '.join(sorted(ret))

def get_hash_filename_base(shader):
    if shader.sub_program.hash_type == 'crc32':
        return shader.sub_program.hash_fmt % shader.sub_program.hash

    if shader.sub_program.hash_type == '3Dmigoto':
        # Emulate 3Dmigto style naming
        if shader.program.name == 'fp': # Pixel Shader ("Fragment Program")
            shader_type = 'ps'
        elif shader.program.name == 'vp': # Vertex Shader
            shader_type = 'vs'
        elif shader.program.name == 'gp': # Geometry Shader
            shader_type = 'gs'
        elif shader.program.name == 'hp': # Hull Shader
            shader_type = 'hs'
        elif shader.program.name == 'dp': # Domain Shader
            shader_type = 'ds'
        # Still missing compute shaders from this list
        else:
            raise Exception("Unknown program type: %s" % shader.program.name)
        return (shader.sub_program.hash_fmt + '-%s') % (shader.sub_program.hash, shader_type)

    assert(False)

def export_filename_combined_long(shaders, args):
    ret = []

    ret.append('Shaders')
    ret.append(shaders[0].sub_program.name.strip())

    # basename, ext = os.path.splitext(shaders[0].shader.filename)
    # ret.append('%s - %s' % (basename, shaders[0].shader.name))
    ret.append(shaders[0].shader.name)

    subshaders = set([ x.sub_shader.counter for x in shaders ])
    ret.append('SubShader %s' % '+'.join(map(str, sorted(subshaders))))

    def pass_name(shader):
        if 'Name' in shader.shader_pass.keywords:
            return strip_quotes(shader.shader_pass.keywords['Name'][0].line.strip())
    passes = set([ x.shader_pass.counter for x in shaders ])
    names = set(filter(None, map(pass_name, shaders)))
    component = 'Pass %s' % '+'.join(map(str, sorted(passes)))
    if names:
        component += ' - ' + ' '.join(sorted(names))
    ret.append(component)

    ret.append(shaders[0].program.name)

    if args and not args.filename_keywords and shaders[0].sub_program.hash:
        ret.append(get_hash_filename_base(shaders[0]))
    else:
        def keywords(shader):
            if 'Keywords' in shader.sub_program.keywords:
                assert(len(shader.sub_program.keywords['Keywords']) == 1)
                return shader.sub_program.keywords['Keywords'][0]
            return set()
        kw = set()
        kw.update(*map(keywords, shaders))
        if kw:
            ret.append(compress_keywords(kw))

    if shaders[0].sub_program.fog:
        ret[-1] = '%s %s' % (ret[-1], shaders[0].sub_program.fog)

    return ret

def export_filename_combined_short(shader, args):
    if not shader.sub_program.hash:
        return None

    if shader.sub_program.hash_type == 'crc32':
        return (
            'ShaderCRCs',
            shader.shader.name,
            shader.program.name,
            get_hash_filename_base(shader),
        )

    if shader.sub_program.hash_type == '3Dmigoto':
        return (
            'ShaderFNVs',
            shader.shader.name,
            get_hash_filename_base(shader),
        )

    assert(False)

def export_filename_combined(sub_programs, args):
    shaders = list(map(get_parents, sub_programs))

    # Different sub programs have different assembly languages and should not match:
    assert(all([ x.sub_program.name == shaders[0].sub_program.name for x in shaders]))

    # Filenames potentially could differ:
    # assert(all([ x.shader.filename == shaders[0].shader.filename for x in shaders]))

    # Should be identical because we explicitly filtered on this:
    assert(all([ x.shader.name == shaders[0].shader.name for x in shaders]))

    # vertex & pixel shaders embed different identifiers in the assembly, so should not match:
    assert(all([ x.program.name == shaders[0].program.name for x in shaders]))

    if not args.deep_dir:
        ret = export_filename_combined_short(shaders[0], args)
    else:
        ret = export_filename_combined_long(shaders, args)
    if ret is not None:
        return [x.replace('/', '_') for x in ret]
    return None

def _collect_headers(tree):
    headers = []
    indent = 0
    if tree.parent is not None:
        (headers, indent) = (_collect_headers(tree.parent))
    else:
        headers.append('Unity headers extracted from %s' % tree.filename)
    headers.append('  ' * indent + tree.header())
    for item in tree:
        if isinstance(item, Tree):
            # Don't get headers for anything else in this file
            continue
        items = str(item).split('\n')
        items = [ '  ' * (indent + 1) + x for x in items ]
        headers.extend(items)
    return (headers, indent + 1)

def collect_headers(tree):
    (headers, nest) = _collect_headers(tree)
    for indent in reversed(range(nest)):
        headers.append('  ' * indent + '}')
    return headers

def _combine_similar_headers(ret, headers):
    head = [ len(x) > 0 and x[0] or '' for x in headers ] # headers on this line

    # Find all future headers:
    future = set()
    for h in headers:
        future.update(h[1:])

    bmplen = math.ceil(len(headers) / 4)

    # Simple case - lines from all headers match:
    if all([ x == head[0] for x in head ]):
        [ len(x) and x.pop(0) for x in headers ]
        ret.append('%s  %s' % (' ' * bmplen, head[0]))
        return

    # Don't dump out any headers that are also found on a future line:
    for i,h in enumerate(head):
        if h in future:
            head[i] = None

    # Could also delay lines with keywords appearing on a future line in the
    # same scope - be careful of 'Tags' keyword appearing in multiple scopes!
    # For now let's see if this is sufficient.

    if not any(head):
        # Avoid potential live lock - certain patterns of headers could
        # potentially cause each header stream to block waiting on the other
        # streams to flush to a matching line.
        # If all streams are blocked, force flushing out the current lines:
        head = [ len(x) > 0 and x[0] or '' for x in headers ]

    # Dump any ungrouped headers:
    tmp = {}
    for i,h in enumerate(head):
        if not h:
            continue
        headers[i].pop(0)
        tmp.setdefault(h, 0)
        tmp[h] |= 1 << i
    for (h, bmp) in sorted(tmp.items()):
        ret.append('%.*x: %s' % (bmplen, bmp, h))

def combine_similar_headers(trees):
    headers = list(map(collect_headers, trees))
    ret = []
    while any(headers):
        _combine_similar_headers(ret, headers)
    return ret

def commentify(headers):
    return '\n'.join([ '// %s' % x for x in headers ])

def indent_like_helix(assembly):
    return '\n'.join([ '%s%s' % (' '*4, x) for x in assembly.split('\n') ]) + '\n'

def mkdir_recursive(components):
    path = os.curdir
    while components:
        path = os.path.join(path, components.pop(0))
        if os.path.isdir(path):
            continue
        os.mkdir(path)

def calc_shader_crc(shader_asm):
    # FUTURE: Use ctypes to call into d3dx.dll directly to remove need for
    # shaderasm.exe helper (may require native windows python - cygwin python
    # is missing some function calling conventions). Can always try both
    # methods.
    import subprocess, zlib
    helper = os.path.join(os.path.dirname(__file__), 'shaderasm.exe')

    # Once Python 3.4 gets into cygwin switch to this:
    # blob = subprocess.check_output([helper], input=shader_asm.encode('ascii'))

    p = subprocess.Popen([helper], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    (blob, _) = p.communicate(shader_asm.encode('ascii'))

    # I'm getting -11 (SEGV) in cygwin python for some reason, which I don't
    # see when running the command line - thinking it may be bogus.
    # if p.returncode != 0:
    #     print("shaderasm.exe helper failed with exit code %i" % p.returncode)
    #     raise subprocess.CalledProcessError()

    if not blob:
        return None

    return zlib.crc32(blob)

def add_shader_hash_crc(sub_program):
    try:
        sub_program.hash = calc_shader_crc(sub_program.shader_asm)
        sub_program.hash_type = 'crc32'
        sub_program.hash_fmt = '%.8X'
    except:
        pass
    if not sub_program.hash:
        print('WARNING: Unable to determine shader CRC32 - is shaderasm.exe installed?')

fnv_offset_basis = 0xcbf29ce484222325
fnv_prime = 0x100000001b3
def fnv64_1(input):
    hash = fnv_offset_basis
    for octet in input:
        assert(octet & 0xff == octet)
        hash = (hash * fnv_prime) & 0xffffffffffffffff
        hash = hash ^ octet
    return hash

def fnv_3Dmigoto_shader(input):
    # 3Dmigoto does not implement FNV correctly as it starts with hash=0
    # instead of hash=fnv_offset_basis, but we need to match it's
    # implementation:
    hash = 0
    for octet in input:
        assert(octet & 0xff == octet)
        hash = (hash * fnv_prime) & 0xffffffffffffffff
        hash = hash ^ octet
    return hash

def add_shader_hash_fnv(sub_program):
    bin = decode_unity_d3d11_shader(sub_program.shader_asm)

    # Does not match 3Dmigoto's hash function:
    # sub_program.hash = fnv64_1(bin)
    # sub_program.hash_type = 'fnv64'

    sub_program.hash = fnv_3Dmigoto_shader(bin)
    sub_program.hash_type = '3Dmigoto'

    sub_program.hash_fmt = '%.16x'

def add_shader_hash(sub_program):
    sub_program.hash = None
    sub_program.hash_type = None
    sub_program.hash_fmt = None
    if sub_program.name == 'd3d9':
        return add_shader_hash_crc(sub_program)
    if sub_program.name.startswith('d3d11'):
        return add_shader_hash_fnv(sub_program)

def add_header_hash(headers, sub_program):
    if sub_program.hash:
        if sub_program.hash_type == 'crc32':
            if sub_program.fog:
                headers[0] = 'CRC32: %.8X (%s + %.8X) | %s' % (sub_program.hash, sub_program.fog, sub_program.fog_orig_crc, headers[0])
            else:
                headers[0] = 'CRC32: %.8X | %s' % (sub_program.hash, headers[0])
        # elif sub_program.hash_type == 'fnv64':
        #     headers[0] = 'FNV64: %.16x | %s' % (sub_program.hash, headers[0])
        elif sub_program.hash_type == '3Dmigoto':
            headers[0] = '3DMigoto: %.16x | %s' % (sub_program.hash, headers[0])
        else:
            raise Exception("Unknown hash type: %s" % sub_program.hash_type)

def index_headers(headers, sub_program):
    # TODO: Also store d3d11 hashes, but no point until there is a tool to look
    # them up
    if sub_program.hash and sub_program.hash_type == 'crc32':
        hash_headers['%.8X' % sub_program.hash] = headers

def save_header_index():
    try:
        out = json.load(open(shader_idx_filename, 'r', encoding='utf-8'))
        out.update(hash_headers)
    except:
        out = hash_headers
    print('Saving header index %s...' % shader_idx_filename)
    json.dump(out, open(shader_idx_filename, 'w', encoding='utf-8'), sort_keys = True, indent = 0)

def add_vanity_tag(headers):
    if headers[-1] != '':
        headers.append('')
    headers.append("Headers extracted with DarkStarSword's extract_unity_shaders.py")
    headers.append("https://raw.githubusercontent.com/DarkStarSword/3d-fixes/master/extract_unity_shaders.py")

def decode_unity_d3d11_shader(asm):
    # Pretty straight forward encoding - each byte is split in half and offset
    # from the letter 'a'.

    # Strip off first line, which is the shader model and not part of the
    # binary file:
    asm = list(asm[asm.find('\n'):])

    def next_char():
        char = ' '
        while char.isspace():
            char = asm.pop(0)
        return char

    ret = []
    while len(asm):
        upper = ord(next_char()) - ord('a')
        lower = ord(next_char()) - ord('a')
        assert(upper & 0xffff == upper)
        assert(lower & 0xffff == lower)
        ret.append((upper << 4) | lower)
    return bytes(ret)

def _export_shader(sub_program, headers, path_components):
    mkdir_recursive(path_components[:-1])
    dest = os.path.join(os.curdir, *path_components)
    headers = commentify(headers)
    index_headers(headers, sub_program)

    if sub_program.name.startswith('d3d11'):
        print('Extracting %s_headers.txt...' % dest)
        with open('%s_headers.txt' % dest, 'w') as f:
            f.write(headers)
            if sub_program.name.startswith('d3d11'):
                f.write('\n//\n')
                f.write('// Shader model %s' % sub_program.shader_asm.split('\n', 1)[0])
        print('Extracting %s_original.bin...' % dest)
        with open('%s_original.bin' % dest, 'wb') as f:
            f.write(decode_unity_d3d11_shader(sub_program.shader_asm))
    else:
        print('Extracting %s.txt...' % dest)
        with open('%s.txt' % dest, 'w') as f:
            f.write(headers)
            f.write('\n\n')
            f.write(indent_like_helix(sub_program.shader_asm))

def export_shader(sub_program, args):
    headers = collect_headers(sub_program)
    add_header_hash(headers, sub_program)
    add_vanity_tag(headers)

    path_components = export_filename_combined([sub_program], args)
    if path_components is None:
        return
    return _export_shader(sub_program, headers, path_components)

def shader_name(tree):
    while tree.parent is not None:
        tree = tree.parent
    return tree.name

def dedupe_shaders(shader_list, args):
    asm = shader_list[0].shader_asm
    assert(all([ x.shader_asm == asm for x in shader_list]))

    headers = []
    shaders = sorted(set(map(shader_name, shader_list)))
    headers.append('Matched %i variants of %i shaders: %s' %
            (len(shader_list), len(shaders), ', '.join(shaders)))
    headers.append('')
    for shader in shaders:
        similar_shaders = filter(lambda x: shader_name(x) == shader, shader_list)
        headers.extend(combine_similar_headers(similar_shaders))
        headers.append('')
    add_header_hash(headers, shader_list[0])
    add_vanity_tag(headers)
    # print(commentify(headers))

    for shader in shaders:
        similar_shaders = filter(lambda x: shader_name(x) == shader, shader_list)
        path_components = export_filename_combined(similar_shaders, args)
        if path_components is None:
            return
        _export_shader(shader_list[0], headers, path_components)

def parse_args():
    global shadertool
    import argparse
    parser = argparse.ArgumentParser(description = 'Unity Shader Extractor')
    parser.add_argument('shaders', nargs='+',
            help='List of compiled Unity shader files to parse')
    parser.add_argument('--filename-keywords', action='store_true',
            help='Name the files by the keywords of the shader (WARNING: May exceed Windows filename limit)')
    parser.add_argument('--deep-dir', action='store_true',
            help='Use alternate directory structure with more levels to sort the shaders (WARNING: May exceed Windows filename limit)')
    parser.add_argument('--fog', action='store_true',
            help='Generate additional shader variants with fog instructions added to match those from Unity')
    parser.add_argument('--type', action='append',
            help='Filter types of shaders to process, useful to avoid unecessary slow hash calculations')
    args = parser.parse_args()
    if args.filename_keywords and not args.deep_dir:
        raise ValueError('--filename-keywords requires --deep-dir')
    if args.fog:
        try:
            shadertool = __import__('shadertool')
        except ImportError:
            raise ImportError('--fog requires shadertool.py')
    return args

def main():
    global shader_list

    args = parse_args()
    processed = set()

    # Windows command prompt passes us a literal *, so expand any that we were passed:
    import glob
    f = []
    for file in args.shaders:
        if '*' in file:
            f.extend(glob.glob(file))
        else:
            f.append(file)
    args.shaders = f

    for filename in args.shaders:
        shader_list = []
        print('Parsing %s...' % filename)
        data = open(filename, 'rb').read()
        digest = hashlib.sha1(data).digest()
        if digest in processed:
            continue
        processed.add(digest)
        tree = list(tokenise(data.decode('ascii'))) # I don't know what encoding it uses
        tree = curly_scope(tree)
        tree = parse_keywords(tree, filename=os.path.basename(filename), args=args)

    if args.fog:
        for shaders in list(shader_index.values()):
            for shader in shaders:
                if shader.name != 'd3d9':
                    continue
                assert(not shader.fog)
                try:
                    for fog_tree in create_fog_asm(shader.shader_asm):
                        fog_asm = str(fog_tree)
                        if fog_asm == shader.shader_asm:
                            continue
                        fog_shader = copy.copy(shader) # Not a deep copy - shader's parent should still link to original, etc
                        del fog_shader.hash
                        fog_shader.fog = fog_tree.fog_type
                        fog_shader.fog_orig_crc = shader.hash
                        handle_shader_asm(fog_asm, fog_shader, fog_asm)
                except SyntaxError as e:
                    import traceback, time
                    traceback.print_exc()
                    time.sleep(0.1)
                    continue

    for shaders in shader_index.values():
        if len(shaders) == 1:
            export_shader(shaders[0], args)
        else:
            # print('-'*79)
            dedupe_shaders(shaders, args)

    save_header_index()

if __name__ == '__main__':
    sys.exit(main())

# vi: sw=4:ts=4:expandtab
