from abc import abstractmethod
import webbrowser
import os
import threading
import tkinter as tk
import time
from tkinter.filedialog import askopenfilename, asksaveasfilename


TITLE = 'HTML Editor'

class ParserError(Exception):
    def __init__(self, message = ''):
        super().__init__(message)

class ParserElement:
    def __init__(self, l: int, r: int, type: str):
        self._l = l
        self._r = r
        self._type = type

    @property
    def l(self) -> int:
        return self._l
    
    @property
    def r(self) -> int:
        return self._r
    
    @property
    def type(self) -> str:
        return self._type

class ParserBase:
    @abstractmethod
    def _parse(self) -> None:
        pass

    @property
    @abstractmethod
    def result(self) -> list[ParserElement]:
        pass

    def __init__(self, text: str, whitespaces: str):
        self._text = text
        self._whitespaces = whitespaces
        self._pos = 0
        self._parse()

    def _is_end(self) -> bool:
        return self._pos >= len(self._text)

    def _match_single(self, prefix: str, is_impotant_register = False) -> bool:
        A = self._text[self._pos:self._pos + len(prefix)]
        B = prefix
        if is_impotant_register:
            return A == B
        else:
            return A.lower() == B.lower()

    def _match(self, prefixes: str | list[str], is_impotant_register = False) -> bool:
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        
        for prefix in prefixes:
            if self._match_single(prefix, is_impotant_register):
                return True
        return False

    def _skip_match(self, prefix: str, is_impotant_register = False) -> None:
        if self._match(prefix, is_impotant_register):
            self._skip_len(len(prefix))
        else:
            raise ParserError()

    def _skip_len(self, cnt: int) -> None:
        if self._pos + cnt > len(self._text):
            raise ParserError()
        else:
            self._pos += cnt

    def _next(self) -> str:
        if self._pos < len(self._text):
            cur = self._char()
            self._pos += 1
            return cur
        else:
            raise ParserError()

    def _char(self) -> str | None:
        if self._pos < len(self._text):
            return self._text[self._pos]
        return None

    def _can_skip_whitespace(self) -> bool:
        return (not self._is_end()) and (self._char() in self._whitespaces)
    
    def _skip_whitespaces(self) -> None:
        if not self._can_skip_whitespace():
            raise ParserError()
        else:
            self._try_skip_whitespaces()

    def _try_skip_whitespaces(self) -> None:
        while self._can_skip_whitespace():
            self._next()

    def _end_filter(self, end):
        return lambda character: not character in end

    def _parse_text(self, text_filter, min_one = False) -> str:
        result = ''

        if min_one:
            if self._is_end() or not text_filter(self._char()):
                raise ParserError()
            result += self._next()
        
        while not self._is_end() and text_filter(self._char()):
            result += self._next()
        
        return result
'''
    WHITESPACES = ' ' '\n' '\t'
    CHARW = <будь-який символ>
    CHAR = <символ крім WHITESPACES>

    name = CHAR+
    text = CHARW*

    string = "\"" text "\""
    value = string | CHAR+
    comment = "<!--" CHAR* "-->"
    
    tag_param = name ("=" value)*

    open_tag  = "<" name tag_param* ">"
    open_and_close_tag = "<" name tag_param* "/>"
    close_tag = "</" name ">"

    doctype = "<!DOCTYPE" text ">" 

    tag_block = open_and_close_tag | (open_tag CHAR* tag_block* CHAR* close_tag)

    HTML_FILE = doctype? (tag_block | comment)*
'''

'''
    HTMLParser types
    error
    tag_name
    tag_param_name
    tag_param_value
    text
    doctype
    script
'''

def parser_result_updater(element_type):
    def _parser_element_handler(func):
        def wrapper(self, *args, **kwargs):
            pos = self._pos
            result = func(self, *args, **kwargs)
            if pos < self._pos:
                self._result.append(ParserElement(pos, self._pos, element_type))
            return result
        return wrapper
    return _parser_element_handler

def parser_error_handler(func):
    def wrapper(self, *args, **kwargs):
        pos = self._pos
        try:
            return func(self, *args, **kwargs)
        except ParserError as e:
            self._result.append(ParserElement(pos, self._pos, 'error'))
    return wrapper

def parser_restorer(func):
    def wrapper(self, *args, **kwargs) -> bool:
        old_pos = self._pos
        old_result = self._result.copy()
        try:
            func(self, *args, **kwargs)
            return True
        except ParserError as e:
            self._pos = old_pos
            self._result = old_result
            return False
    return wrapper

class HTMLParser(ParserBase):
    WHITESPACES = " \n\t"

    def __skip_name(self) -> str: 
        return self._parse_text(text_filter = self._end_filter('!/<>"=' + HTMLParser.WHITESPACES), min_one = True)
    
    def __skip_value(self) -> str:
        if self._match('"'):
            self._skip_match('"')
            result = self._parse_text(text_filter = self._end_filter('"'))
            self._skip_match('"')
            return '"' + result + '"'
        else:
            return self._parse_text(text_filter = self._end_filter('!/<>"=' + HTMLParser.WHITESPACES), min_one = True)
    
    @parser_restorer
    @parser_result_updater('doctype')
    def __try_parse_doctype(self) -> None:
        self._skip_match('<!doctype', is_impotant_register = False)
        self._skip_whitespaces()
        self._parse_text(text_filter = self._end_filter('>'), min_one = True)
        self._skip_match('>')

    @parser_result_updater('tag_name')
    def __parse_tag_name(self) -> str:
        return self.__skip_name()
    
    @parser_result_updater('tag_param_name')
    def __parse_tag_param_name(self) -> str:
        return self.__skip_name()
        
    @parser_result_updater('tag_param_value')
    def __parse_tag_param_value(self) -> str:
        return self.__skip_value()

    @parser_result_updater('script')
    def __parse_script(self) -> None:
        while not self._is_end():
            self._parse_text(text_filter = self._end_filter('<'), min_one = False)
            lpos = self._pos
            if self.__try_parse_close_tag2('script'):
                self._pos = lpos
                break
            while not self._is_end() and self._char() == '<':
                self._next()

    @parser_result_updater('style')
    def __parse_style(self) -> None:
        while not self._is_end():
            self._parse_text(text_filter = self._end_filter('<'), min_one = False)
            lpos = self._pos
            if self.__try_parse_close_tag2('style'):
                self._pos = lpos
                break
            while not self._is_end() and self._char() == '<':
                self._next()

    @parser_restorer
    @parser_result_updater('comment')
    def __try_parse_comment(self) -> None:
        self._skip_match('<!--')
        self._try_skip_whitespaces()
        while not self._match('-->'):
            self._next()
        self._try_skip_whitespaces()
        self._skip_match('-->')

    @parser_result_updater('text')
    def __try_parse_user_text(self) -> None:
        self._parse_text(text_filter = self._end_filter('<'), min_one = False)

    def __try_parse_tag_param(self) -> None:
        self.__parse_tag_param_name()
        self._try_skip_whitespaces()
        if self._match('='):
            self._skip_match('=')
            self._try_skip_whitespaces()
            self.__parse_tag_param_value()
            self._try_skip_whitespaces()

    @parser_error_handler
    def __try_parse_tag_params(self) -> None:
        self._try_skip_whitespaces()
        while not self._is_end() and not self._match(['/>', '>']):
            self.__try_parse_tag_param()
            self._try_skip_whitespaces()

    @parser_restorer
    def __try_parse_open_and_close_tag(self) -> None:
        self._skip_match('<')
        self._try_skip_whitespaces()
        name = self.__parse_tag_name()
        self._try_skip_whitespaces()
        self.__try_parse_tag_params()
        self._skip_match('/>')

    @parser_error_handler
    def __try_parse_open_tag(self) -> str:
        self._skip_match('<')
        self._try_skip_whitespaces()
        name = self.__parse_tag_name()
        self._try_skip_whitespaces()
        self.__try_parse_tag_params()
        self._skip_match('>')
        return name
    
    def __parse_close_tag(self, open_tag_name: str | None = None) -> None:
        self._skip_match('</')
        self._try_skip_whitespaces()
        close_tag_name = self.__parse_tag_name()
        if open_tag_name and open_tag_name != close_tag_name:
            raise ParserError()
        self._try_skip_whitespaces()
        self._skip_match('>')

    @parser_restorer
    def __try_parse_close_tag2(self, open_tag_name: str | None = None) -> None:
        self.__parse_close_tag(open_tag_name)
    
    @parser_error_handler
    def __try_parse_close_tag(self, open_tag_name: str | None = None) -> None:
        self.__parse_close_tag(open_tag_name)
    
    @parser_error_handler
    def __parse_tag_block(self) -> None:
        if self._match('</'):
            self.__try_parse_close_tag()
        else:

            if self.__try_parse_open_and_close_tag():
                return
        
            tag_name = self.__try_parse_open_tag()
            if tag_name in ['script', 'style']:
                if tag_name == 'script':
                    self.__parse_script()
                else:
                    self.__parse_style()
                self.__try_parse_close_tag(tag_name)

    def __try_parse_tag_blocks(self) -> None:
        while not self._is_end() and self._char() == '<':
            self.__try_parse_comment()
            self.__parse_tag_block()
            self._try_skip_whitespaces()
            self.__try_parse_user_text()

    def _parse(self) -> None:
        self._result = []
        self._try_skip_whitespaces()

        self.__try_parse_doctype()
        
        self._try_skip_whitespaces()
        self.__try_parse_user_text()

        self.__try_parse_tag_blocks()

    @property
    def result(self) -> list[ParserElement]:
        return self._result

    def __init__(self, html_text: str):
        super().__init__(html_text, HTMLParser.WHITESPACES)

class HTMLEditor:
    class AutoParser(threading.Thread):
        def __init__(self, html_editor):
            threading.Thread.__init__(self)
            self._html_editor = html_editor
        
        def run(self):
            while True:
                if self._html_editor._reset_is_modified():
                    text = self._html_editor.get_text()

                    parsed_html = HTMLParser(text)
                    pos_converter = HTMLEditor.PositionConverter(text)

                    self._html_editor._update_colors(parsed_html.result, pos_converter, text)
                
                time.sleep(0.2)

    class PositionConverter:
        def __init__(self, text: str):
            self.__n_sizes = []
            
            last_pos = -1
            while True:
                try:
                    new_pos = text.index('\n', last_pos + 1)
                    self.__n_sizes.append(new_pos - last_pos )
                    last_pos = new_pos
                except:
                    break
            
        def convert(self, index: int) -> float:
            line = 1
            
            for i in self.__n_sizes:
                if i <= index:
                    index -= i
                    line += 1
                else:
                    break

            return f'{line}.{index}'

    def __configure_tags(self, txt_editor: tk.Text) -> None:
        txt_editor.tag_configure("default", foreground="#656D78")
        txt_editor.tag_configure("tag_name", foreground="#4A89DC")
        txt_editor.tag_configure("tag_param_name", foreground="#5D9CEC")
        txt_editor.tag_configure("tag_param_value", foreground="#967ADC")
        txt_editor.tag_configure("doctype", foreground="#37BC9B")
        txt_editor.tag_configure("comment", foreground="#AAB2BD")
        txt_editor.tag_configure("text", foreground="#434A54")
        txt_editor.tag_configure("script", foreground="#E9573F")
        txt_editor.tag_configure("style", foreground="#D770AD")
        txt_editor.tag_configure("error", foreground='#DA4453')

    def __init__(self, txt_editor: tk.Text):
        self._txt_editor = txt_editor
        self._temp_editor = tk.Text()

        self._lock = threading.Lock()

        self.__configure_tags(self._txt_editor)
        self.__configure_tags(self._temp_editor)

        self._auto_parser = HTMLEditor.AutoParser(self)
        self._auto_parser.setDaemon(True)
        self._auto_parser.start()

    def _remove_tags(self): 
        for tag_name in self._txt_editor.tag_names():
            self._txt_editor.tag_remove(tag_name, 1.0, tk.END)
        
        self._txt_editor.tag_add('default', 1.0, tk.END)

    def set_text(self, text: str) -> None:
        self._txt_editor.delete(1.0, tk.END)
        self._txt_editor.insert(tk.END, text)
    
    def _update_colors(self, info: list[ParserElement], pos_converter, text) -> None:
        tags = {}

        for tag_name in self._txt_editor.tag_names():
            tags[tag_name] = set()
            ranges = self._txt_editor.tag_ranges(tag_name)
            for i in range(len(ranges) // 2):
                tags[tag_name].add((str(ranges[2 * i]), str(ranges[2 * i + 1])))

        _temp_editor = tk.Text()
        self.__configure_tags(_temp_editor)
        _temp_editor.insert(tk.END, text)

        for parser_element in info:
            l, r = [pos_converter.convert(parser_element.l), pos_converter.convert(parser_element.r)]

            _temp_editor.tag_add(parser_element.type, l, r)

        tags_new = {}
        
        for tag_name in _temp_editor.tag_names():
            tags_new[tag_name] = set()
            ranges = _temp_editor.tag_ranges(tag_name)
            for i in range(len(ranges) // 2):
                tags_new[tag_name].add((str(ranges[2 * i]), str(ranges[2 * i + 1])))
        
        keys = set([*tags.keys(), *tags_new.keys()])
        tags_to_remove = {}
        tags_to_add = {}

        for key in keys:
            if not key in tags:
                tags_to_add[key] = tags_new[key]
            elif not key in tags_new:
                tags_to_remove[key] = tags[key]
            else:
                tags_to_add[key] = tags_new[key].difference(tags[key]) 
                tags_to_remove[key] = tags[key].difference(tags_new[key]) 
        
        for k, v in tags_to_remove.items():
            for r in v:
                self._txt_editor.tag_remove(k, r[0], r[1])
        
        for k, v in tags_to_add.items():
            for r in v:
                self._txt_editor.tag_add(k, r[0], r[1])

    def get_text(self) -> str:
        return self._txt_editor.get(1.0, tk.END)
    
    def insert(self, text) -> None:
        self._txt_editor.insert(tk.INSERT, text)

    def _reset_is_modified(self) -> bool:
        with self._lock:
            result = self._txt_editor.edit_modified()
            self._txt_editor.edit_modified(False)
            return result

class Application:
    def _open_file(self):
        filepath = askopenfilename(
            filetypes = [("HTML Files", "*.html")]
        )
        if not filepath:
            return

        with open(filepath, "r", encoding='utf-8') as input_file:
            text = input_file.read()
            self._txt_editor.set_text(text)
        
        self._root_window.title(f"{TITLE} ({filepath})")
    
    def _save_file(self):
        filepath = asksaveasfilename(
            defaultextension = "html",
            filetypes = [("HTML Files", "*.html")],
        )
        if not filepath:
            return
        with open(filepath, "w", encoding='utf-8') as output_file:
            text = self._txt_editor.get_text()
            output_file.write(text)
        
        self._root_window.title(f"{TITLE} ({filepath})")

    def _open_in_web(self):
        filepath = os.getcwd() + '/temp.html'
        with open(filepath, "w", encoding='utf-8') as output_file:
            text = self._txt_editor.get_text()
            output_file.write(text)
        webbrowser.open(f'file://{filepath}')
    
    def _paste_template(self): 
        self._txt_editor.set_text(
            '<!DOCTYPE html>\n'
            '<html lang="en">\n'
            '<head>\n'
            '\t<meta charset="UTF-8">\n'
            '\t<meta http-equiv="X-UA-Compatible" content="IE=edge">\n'
            '\t<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '\t<title>Document</title>\n'
            '</head>\n'
            '<body>\n'
            '\n'
            '</body>\n'
            '</html>\n'
        )
    
    def _paste_image(self):
        if self._add_image:
            return

        self._add_image = tk.Toplevel(self._root_window)

        width = tk.IntVar(self._add_image)
        height = tk.IntVar(self._add_image)


        def _paste_concrete():
            filepath = askopenfilename(
                defaultextension = "png",
                filetypes = [("PNG", "*.png"), ("JPEG", "*.jpeg"), ("JPG", "*.jpg")],
            )
            if filepath:
                text = f'<img src="{filepath}"'
                if width.get() > 0:
                    text += f' width="{width.get()}"'
                if height.get() > 0:
                    text += f' height="{height.get()}"'
                text += '>'
                self._txt_editor.insert(text)

            self._add_image.destroy()
            self._add_image = None
        
        tk.Label(self._add_image, text="width:").pack(padx=5, pady=5)
        tk.Entry(self._add_image, textvariable=width).pack(padx=5, pady=5)
        tk.Label(self._add_image, text="height:").pack(padx=5, pady=5)
        tk.Entry(self._add_image, textvariable=height).pack(padx=5, pady=5)
        tk.Button(self._add_image, text="Add image", command=_paste_concrete).pack(padx=5, pady=20)

    def _paste_div_block(self):
        if self._add_div:
            return

        self._add_div = tk.Toplevel(self._root_window)
        
        id = tk.StringVar(self._add_div)
        class_name = tk.StringVar(self._add_div)

        def _paste_concrete():
            text = f'<div'
            if len(id.get()) > 0:
                text += f' id="{id.get()}"'
            if len(class_name.get()) > 0:
                text += f' class="{class_name.get()}"'
            text += "></div>"
            self._txt_editor.insert(text)

            self._add_div.destroy()
            self._add_div = None


        tk.Label(self._add_div, text="id:").pack(padx=5, pady=5)
        tk.Entry(self._add_div, textvariable=id).pack(padx=5, pady=5)
        tk.Label(self._add_div, text="class:").pack(padx=5, pady=5)
        tk.Entry(self._add_div, textvariable=class_name).pack(padx=5, pady=5)
        tk.Button(self._add_div, text="Add div", command=_paste_concrete).pack(padx=5, pady=20)
    
    def __configure_root_window(self):
        self._add_image = None
        self._add_div = None
        self._root_window = tk.Tk()
        self._root_window.title(TITLE)

        self._root_window.rowconfigure(0, minsize = 400, weight = 1)
        self._root_window.columnconfigure(0, minsize = 600, weight = 1)

    def __configure_menu(self):
        self._menu = tk.Menu(self._root_window)
        self._root_window.config(menu = self._menu)

        self._menu.add_command(label = "Open File", command = self._open_file)
        self._menu.add_command(label = "Save As...", command = self._save_file)
        self._menu.add_command(label = "Open in Web", command = self._open_in_web)
        self._menu.add_command(label = "Default template", command = self._paste_template)
        self._menu.add_command(label = "Add image", command = self._paste_image)
        self._menu.add_command(label = "Add div", command = self._paste_div_block)

    def __configure_editor(self):
        txt_edit = tk.Text(self._root_window)
        txt_edit.grid(row = 0, column = 0, sticky = "nsew")

        self._txt_editor = HTMLEditor(txt_edit)

    def __init_ui(self):
        self.__configure_root_window()
        self.__configure_menu()
        self.__configure_editor()
    
    def __init__(self):
        self.__init_ui()
    
    def main_loop(self):
        self._root_window.mainloop()

if __name__ == '__main__':
    app = Application()
    app.main_loop()