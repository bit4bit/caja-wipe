import os
import urllib
import subprocess
import threading
import time
from gi.repository import Caja, GObject, Gtk
from gettext import ngettext,gettext


class DialogWipe(Gtk.Dialog):

    def __init__(self, parent):
        Gtk.Dialog.__init__(self, "Wiping", parent, 0,
                            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL))
        
        self.stopped = False
        
        box = self.get_content_area()
        
        self.lbprocess = Gtk.Label("...")
        box.add(self.lbprocess)
        
        self.show_all()

        
    def body_text(self, txt):
        self.lbprocess.set_markup(txt)
        
class DialogOptionsWipe(Gtk.Dialog):

    def __init__(self, parent, title):
        Gtk.Dialog.__init__(self, "Options for Wipe", parent, 0,
                            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                             Gtk.STOCK_OK, Gtk.ResponseType.OK))

        
        self.lbtitle = Gtk.Label()
        self.lbtitle.set_markup(title)
        box = self.get_content_area()


        self.checkFastMode = Gtk.CheckButton("Fast an  insecure mode  (no /dev/urandom, no synchronize mode)")
        self.checkWriteZeros = Gtk.CheckButton("Last write with zeros instead of random data")

        box.add(self.lbtitle)
        box.add(Gtk.Label(gettext('If you wipe an item, it will not be recoverable.')))
        box.add(self.checkFastMode)
        box.add(self.checkWriteZeros)
        self.show_all()
    
class CajaWipe(GObject.GObject, Caja.MenuProvider):
    
    def __init__(self):
        self.resources = []

    def get_file_items(self, window, files):
        item = Caja.MenuItem(
            name='CajaWipe::wiper',
            label=ngettext('Wipe this folder', 'Wipe these folders', len(files)),
            tip=ngettext('Wipe this folder', 'Wipe these folders', len(files)),
            icon=Gtk.STOCK_CLEAR
        )
        files_to_delete = []
        for file in files:
            filename = urllib.unquote(file.get_uri()[7:])
            files_to_delete.append(filename)
            
        item.connect('activate', self.wipe, (window, files_to_delete))
        return [item]

    def cancel_wipe(self, widget):
        pass

    def srm_output(self, dialog, prg):

        rott = {'-': '/', '/': '|', '|': '\\', '\\': '-'}
        
        state = 'poll'
        data = ""
        filename = ""
        while prg.poll() is None:
            if dialog.stopped:
                break
            char = prg.stdout.read(1)

            if state == 'poll':
                if data.strip()[-6:] == "Wiping":
                    state = 'file'
                    filename = ""
                    data = ""
                else:
                    data += char
            elif state  == 'file':
                if char == '*':
                    state = 'progress'
                    data = '-'
                    continue
                else:
                    filename += char
            elif state == 'progress':
                if dialog.stopped:
                    break
                if char != '*':
                    prg.stdout.readline()
                    state = 'poll'
                    data = ""
                    filename = ""
                else:
                    data = rott[data]

            if state == 'progress':
                dialog.body_text(gettext("Wiping {} {}").format(filename, data))
                
        try:
            prg.wait()
        except Exception:
            pass
        dialog.destroy()

    
    def wipe(self, menu, userdata):
        window, files = userdata


        txt = ngettext("<b>Are you sure you want to wipe \"{}\"?</b>", "<b>Are you sure you want to wipe the {} selected items?</b>", len(files))
        if len(files) == 1:
            title = txt.format(files[0])
        else:
            title = txt.format(len(files))

        dialogOptions = DialogOptionsWipe(window, title)
        response = dialogOptions.run()
        dialogOptions.destroy()

        if response == Gtk.ResponseType.OK:
            cmd = ["srm", "-r", "-d", "-v"]
            
            if dialogOptions.checkFastMode.get_active():
                print("fast")
                cmd.append("-f")
            if dialogOptions.checkWriteZeros.get_active():
                print("zero")
                cmd.append("-z")

            cmd.extend(files)
            prg = subprocess.Popen(cmd, bufsize=0, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            dialogWipe = DialogWipe(window)
            t = threading.Thread(target=self.srm_output,args=(dialogWipe, prg))
            t.setDaemon(True)
            t.start()
            dialogWipe.run()
            dialogWipe.stopped = True
            time.sleep(0.5)
            try:
                prg.terminate()
            except  Exception:
                pass
            
            dialogWipe.destroy()
            


        
