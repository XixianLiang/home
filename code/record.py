import os, signal, time, re
import subprocess
import pyperclip
from device import Device
import demjson
from view import View

class Record(object):
    """
    The process for recording DMFs

    Attributes:
        screenshot_num: the number of the screenshots taken during recording
        ui_inst_num: the number of the uiautomator instructions generated during recording
        ui_layout_num: the number of the recorded DMF's layouts
        
    """
    instance = None
    screenshot_num, ui_inst_num, current_layout_num = 0, 0, 0
    DMFtype, datatype = "", ""
    events, views, xmllist = [], [], []
    results, preconditions, postconditions = [], [], []
    HINT_RECORD_STEPS = "Record the steps of DMF in the webiter. Enter 2 to screenshot before recording each step. After all the recordings are completed, enter 1 to stop:"
    HINT_RECORD_DATA_TYPE = "Please enter the type of target data objects of DMF:"
    HINT_RECORD_DMF_TYPE = "Please enter the type of DMF:"

    def __init__(self, root_path:str, device_serial:Device, app, json_name:str):
        Record.instance = self
        self.root_path=root_path
        self.device = Device(device_serial)
        self.app=app
        self.json_name = json_name
         
    def findkeyword(self,key,keyword):
        num1=key.find(keyword+"=")
        returnkey = key[num1+len(keyword)+2:len(key)]
        num2=returnkey.find("\"")
        if num2>-1:
            returnkey = returnkey[0:num2]
        return returnkey

    def findviewbytext(self,now_layout, text, not_view):
        view=None
        for line in now_layout:
            if "<node" not in line:
                continue
            view = View(line,[])
            if text != view.text:
                continue
            else:
                if not_view!=None:
                    if not_view.resourceId == view.resourceId and not_view.className == view.className:
                        break
                return view
        return None
    
    def findviewbytextclassName(self, now_layout, text, className):
        view=None
        for line in now_layout:
            if "<node" not in line:
                continue
            view = View(line,[])
            if className != view.className or text!=view.text:
                continue
            else:
                return view
        return None

    def findviewinstance(self,now_layout, resourceId, className, text):
        view=None
        instance = 0
        for line in now_layout:
            if "<node" not in line:
                continue
            view = View(line,[])
            if resourceId!=None and resourceId == view.resourceId:
                if view.text == text:
                    return instance
                else:
                    instance = instance+1
            elif className!=None and className == view.className:
                if view.text == text:
                    return instance
                else:
                    instance = instance+1
            else:
                continue
        return None

    def get_info(self, line:str, ui_layout_num:int, type:str, datatype:str):
        print("line:"+line)
        resourceId=""
        text=""
        description=""
        xpath=""
        instance=""
        action="#any#"
        className=""
        edittext=""
        force="True"
        if "xpath" in line:
            num1=line.find("xpath(")
            returnkey = line[num1+7:len(line)]
            num2=returnkey.find("\').")
            if num2>-1:
                returnkey = returnkey[0:num2]
            xpath = returnkey
        else:
            keys = line.split("\",")
            for key in keys:
                if "resourceId=" in key:
                    keyword = "resourceId"
                    returnkey = self.findkeyword(key,keyword)
                    resourceId = returnkey
                elif "className=" in key:
                    keyword = "className"
                    returnkey = self.findkeyword(key,keyword)
                    className = returnkey
                elif "description=" in key:
                    keyword = "description"
                    returnkey = self.findkeyword(key,keyword)
                    description = returnkey
                elif "xpath=" in key:
                    keyword = "xpath"
                    returnkey = self.findkeyword(key,keyword)
                    xpath = returnkey
                elif "instance=" in key:
                    keyword = "instance"
                    returnkey = key[key.find("instance=")+9:key.find("instance=")+10]
                    instance = returnkey
                elif "text=" in key:
                    keyword = "text"
                    returnkey = self.findkeyword(key,keyword)
                    text = returnkey
                
        if "long_click" in line or "longclick" in line:
            action = "longclick"
        elif "click" in line:
            action = "click"
        elif "set_text" in line:
            action = "edit"
            num1=line.find("set_text(")
            returnkey = line[num1+10:len(line)]
            num2=returnkey.find("\")")
            if num2>-1:
                returnkey = returnkey[0:num2]
        elif "scroll" in line:
            if "forward" in line and "vert" in line:
                action = "scroll_forward"
            elif "backward" in line and "vert" in line:
                action = "scroll_backward"
            elif "horiz" in line and "toEnd" in line:
                action = "scroll_right"
            else:
                action = "scroll_left"    
        elif "drag" in line:
            action = "drag"
            num1 = line.find("drag(")
            returnkey = line[num1+5:len(line)]
            num2=returnkey.find(")")
            if num2>-1:
                returnkey = returnkey[0:num2]
            edittext = returnkey
        elif "send_keys" in line:
            action = "edit"
            num1=line.find("send_keys(")
            returnkey = line[num1+11:len(line)]
            num2=returnkey.find("\",")
            if num2>-1:
                returnkey = returnkey[0:num2]
            edittext = returnkey
            className = "android.widget.EditText"
        elif "press(\"back\")" in line:
            action = "back"
        
        if type=="search" and action=="edit":
            edittext = datatype+"::random"
        elif action=="edit":
            edittext="random"
        print("resourceId:"+resourceId)
        print("text:"+text)
        print("description:"+description)
        print("xpath:"+xpath)
        print("action:"+action)
        print("edittext:"+edittext)
        print("instance:"+instance)
        print("******************")
        widget = {"name":"e"+str(ui_layout_num+1)+"_widget","UI_layout_num":str(ui_layout_num),"text":text,"resource-id":resourceId,"class":className,"content-desc":description,"xpath":xpath,"instance": instance}
        event = {"widget":"e"+str(ui_layout_num+1)+"_widget","action": action,"text": edittext,"force":True}
        if action !="#any#":
            returnvalue = (widget,event)
            return returnvalue
        else:
            return None
    
    def mkdirTemp(self):
        self.root_path=self.root_path+self.json_name+"/"
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path)
        if not os.path.exists(self.root_path+"/temp"):
            os.makedirs(self.root_path+"/temp")

    def recordDMF(self):
        screenshot_num = 0
        DMFtype = input("Please enter the type of DMF:")
        datatype = input("Please enter the type of target data objects of DMF:")
        HINT_RECORD_STEPS = "\nRecord the steps of DMF in the webiter. Enter 2 to screenshot before recording each step. After all the recordings are completed, enter 1 to stop:"
        endstr = input(HINT_RECORD_STEPS)
        xmllist = []
        while endstr != "1":
            if endstr == "2":
                self.device.use.screenshot(self.root_path+"/temp/"+str(screenshot_num)+".png")
                xml = self.device.use.dump_hierarchy()
                f = open(self.root_path+"/temp/"+str(screenshot_num)+".xml",'w',encoding='utf-8')
                f.write(xml)
                f = open(self.root_path+"/temp/"+str(screenshot_num)+".xml",'r',encoding='utf-8')
                lines=f.readlines()
                xmllist.append(lines)
                screenshot_num=screenshot_num+1
            endstr = input(HINT_RECORD_STEPS)

        #Parsing the recording script of weditor to obtain DMF
        self.device.use.screenshot(self.root_path+"/temp/"+str(screenshot_num)+".png")
        xml = self.device.use.dump_hierarchy()
        f = open(self.root_path+"/temp/"+str(screenshot_num)+".xml",'w',encoding='utf-8')
        f.write(xml)
        f = open(self.root_path+"/temp/"+str(screenshot_num)+".xml",'r',encoding='utf-8')
        lines=f.readlines()
        xmllist.append(lines)
        screenshot_num=screenshot_num+1

        self.screenshot_num = screenshot_num
        self.DMFtype = DMFtype
        self.datatype = datatype
        self.xmllist = xmllist
        print(f"\n\nlen(xmllist) = {len(self.xmllist)}\n\n")

    def getUiautomatorInst(self):
        # Hint that the uiautomator instrcution should be copied
        HINT_COPY_INST = "Now copy the generated uiautomator instructions in the webitor, and enter 1 to next step:" 
        while True:
            endstr = input(HINT_COPY_INST)
            if endstr == "1":
                dd = pyperclip.paste()
                if re.match(r"^d\(", dd.strip()):
                    break
                else:
                    print("It seems that you've copied the wrong uiautomator instruction, please try again.")
        
        # Handle the copied uiautomator instruction
        events = self.events
        views = self.views

        dd=pyperclip.paste()
        lines = dd.split("\n")

        for line in lines:
            if line.strip()!="":
                returnvalue=self.get_info(line, self.current_layout_num, self.DMFtype, self.datatype)
                if returnvalue!=None:
                    self.current_layout_num=self.current_layout_num+1
                    views.append(returnvalue[0])
                    events.append(returnvalue[1])

        
        self.events = events
        self.views = views
        self.ui_inst_num = self.current_layout_num
        print(f"ui_inst_num = {self.ui_inst_num}")

    def processAdd(self, xmllist:list, views: list):
        """The submethod of processRecording

        param:
            xmllist: the xmllist list
            views: the view list
        """
        add_name = input("Please enter the data object you added in these steps:")
        add_name_widget=None
        add_object = None
        i=0
        while i<len(xmllist)-1:
            add_name_widget = self.findviewbytext(xmllist[i],add_name,None)
            if add_name_widget!=None:
                add_name_layout = i
                if add_name_widget.resourceId!="":
                    add_name_instance=self.findviewinstance(xmllist[i], add_name_widget.resourceId, None, add_name)
                    add_name_resourceId = add_name_widget.resourceId
                    add_name_className = ""
                elif add_name_widget.className!="":
                    add_name_instance=self.findviewinstance(xmllist[i], None, add_name_widget.className, add_name)
                    add_name_resourceId = ""
                    add_name_className = add_name_widget.className
                else:
                    print("wrong")
                break
            i=i+1
        add_object = self.findviewbytext(xmllist[len(xmllist)-1],add_name,None)
        add_object_resourceId = ""
        add_object_className = ""
        if add_object!=None:
            if add_object.resourceId!="":
                add_object_resourceId = add_object.resourceId
            elif add_object.className!="":
                add_object_className = add_object.className
            else:
                print("wrong")
        views.append({"name": "add_name","UI_layout_num": str(add_name_layout),"text": "","resource-id": add_name_resourceId,"class": add_name_className,"content-desc": "","xpath": "","instance": str(add_name_instance)})
        views.append({"name": "add_object","UI_layout_num":str(self.current_layout_num),"text": "add_name.text","resource-id": add_object_resourceId,"class": add_object_className,"content-desc": "","xpath": "","instance": ""})
        results=[{"operator": "add","object": "add_name.text"}]
        preconditions=[{"widget": "e1_widget","relation": "in","UI_layout_num": "0","datatype":""},
            {"UI_layout_num": "0","datatype": self.datatype,"relation": "smaller","widget": ""}]
        postconditions=[{"widget": "add_object","relation": "in","UI_layout_num": str(self.current_layout_num),"datatype":""}]
        
        return results, preconditions, postconditions

    def processDelete(self, xmllist:list, views: list):
        delete_name = input("Please enter the data object you deleted in these steps:")
        delete_name_widget=None
        i=0
        while i<len(xmllist)-1:
            delete_name_widget = self.findviewbytext(xmllist[i],delete_name,None)
            if delete_name_widget!=None:
                delete_name_layout = i
                if delete_name_widget.resourceId!="":
                    delete_name_instance=self.findviewinstance(xmllist[i], delete_name_widget.resourceId, None, delete_name)
                    delete_name_resourceId = delete_name_widget.resourceId
                    delete_name_className = ""
                elif delete_name_widget.className!="":
                    delete_name_instance=self.findviewinstance(xmllist[i], None, delete_name_widget.className, delete_name)
                    delete_name_resourceId = ""
                    delete_name_className = delete_name_widget.className
                else:
                    print("wrong")
                break
            i=i+1
        views.append({"name": "delete_name","UI_layout_num": str(delete_name_layout),"text": "","resource-id": delete_name_resourceId,"class": delete_name_className,"content-desc": "","xpath": "","instance": str(delete_name_instance)})
        views.append({"name": "delete_object","UI_layout_num":str(self.current_layout_num),"text": "delete_name.text","resource-id": delete_name_resourceId,"class": delete_name_className,"content-desc": "","xpath": "","instance": ""})
        results=[{"operator": "delete","object": "delete_name.text"}]
        preconditions=[{"widget": "e1_widget","relation": "in","UI_layout_num": "0","datatype":""},
            {"UI_layout_num": "0","datatype": self.datatype,"relation": "is not empty","widget": ""}]
        postconditions=[{"widget": "delete_object","relation": "not in","UI_layout_num": str(self.current_layout_num),"datatype":""}]
        return results, preconditions, postconditions

    def processEdit(self, xmllist:list, views:list):
        add_name = input("Please enter the data object you added in these steps:")
        add_name_widget=None
        add_object = None

        i=0
        while i<len(xmllist)-1:
            add_name_widget = self.findviewbytext(xmllist[i],add_name,None)
            if add_name_widget!=None:
                add_name_layout = i
                if add_name_widget.resourceId!="":
                    add_name_instance=self.findviewinstance(xmllist[i], add_name_widget.resourceId, None, add_name)
                    add_name_resourceId = add_name_widget.resourceId
                    add_name_className = ""
                elif add_name_widget.className!="":
                    add_name_instance=self.findviewinstance(xmllist[i], None, add_name_widget.className, add_name)
                    add_name_resourceId = ""
                    add_name_className = add_name_widget.className
                else:
                    print("wrong")
                break
            i=i+1

        add_object = self.findviewbytext(xmllist[len(xmllist)-1],add_name,None)
        add_object_resourceId = ""
        add_object_className = ""
        if add_object!=None:
            if add_object.resourceId!="":
                add_object_resourceId = add_object.resourceId
            elif add_object.className!="":
                add_object_className = add_object.className
            else:
                print("wrong")
        views.append({"name": "add_name","UI_layout_num": str(add_name_layout),"text": "","resource-id": add_name_resourceId,"class": add_name_className,"content-desc": "","xpath": "","instance": str(add_name_instance)})
        views.append({"name": "add_object","UI_layout_num":str(self.current_layout_num),"text": "add_name.text","resource-id": add_object_resourceId,"class": add_object_className,"content-desc": "","xpath": "","instance": ""})

        delete_name = input("Please enter the data object you deleted in these steps:")
        delete_name_widget=None
        i=0
        while i<len(xmllist)-1:
            delete_name_widget = self.findviewbytext(xmllist[i],delete_name,None)
            if delete_name_widget!=None:
                delete_name_layout = i
                if delete_name_widget.resourceId!="":
                    delete_name_instance=self.findviewinstance(xmllist[i], delete_name_widget.resourceId, None, delete_name)
                    delete_name_resourceId = delete_name_widget.resourceId
                    delete_name_className = ""
                elif delete_name_widget.className!="":
                    delete_name_instance=self.findviewinstance(xmllist[i], None, delete_name_widget.className, delete_name)
                    delete_name_resourceId = ""
                    delete_name_className = delete_name_widget.className
                else:
                    print("wrong")
                break
            i=i+1
        views.append({"name": "delete_name","UI_layout_num": str(delete_name_layout),"text": "","resource-id": delete_name_resourceId,"class": delete_name_className,"content-desc": "","xpath": "","instance": str(delete_name_instance)})
        views.append({"name": "delete_object","UI_layout_num":str(self.current_layout_num),"text": "delete_name.text","resource-id": delete_name_resourceId,"class": delete_name_className,"content-desc": "","xpath": "","instance": ""})

        results=[{"operator": "delete","object": "delete_name.text"},{"operator": "add","object": "add_name.text"}]
        preconditions=[{"widget": "e1_widget","relation": "in","UI_layout_num": "0","datatype":""},
            {"UI_layout_num": "0","datatype": self.datatype,"relation": "is not empty","widget": ""}]
        postconditions=[{"widget": "add_object","relation": "in","UI_layout_num": str(self.current_layout_num),"datatype":""},{"widget": "delete_object","relation": "not in","UI_layout_num": str(self.current_layout_num),"datatype":""}]

        return results, preconditions, postconditions

    def processSearch(self, xmllist:list, views:list):
        search_name = input("Please enter the data object you searched in these steps:")
        search_name_widget=None
        search_object = None
        i=0
        while i<len(xmllist)-1:
            search_name_widget = self.findviewbytextclassName(xmllist[i],search_name,"android.widget.EditText")
            if search_name_widget!=None:
                search_name_layout = i
                if search_name_widget.resourceId!="":
                    search_name_instance=self.findviewinstance(xmllist[i], search_name_widget.resourceId, None, search_name)
                    search_name_resourceId = search_name_widget.resourceId
                    search_name_className = ""
                elif search_name_widget.className!="":
                    search_name_instance=self.findviewinstance(xmllist[i], None, search_name_widget.className, search_name)
                    search_name_resourceId = ""
                    search_name_className = search_name_widget.className
                else:
                    print("wrong")
                break
            i=i+1
        search_object = self.findviewbytext(xmllist[len(xmllist)-1],search_name,search_name_widget)
        search_object_resourceId = ""
        search_object_className = ""
        if search_object!=None:
            if search_object.resourceId!="":
                search_object_resourceId = search_object.resourceId
            elif search_object.className!="":
                search_object_className = search_object.className
            else:
                print("wrong")
        if search_name_widget!=None:
            views.append({"name": "search_name","UI_layout_num": str(search_name_layout),"text": "","resource-id": search_name_resourceId,"class": search_name_className,"content-desc": "","xpath": "","instance": str(search_name_instance)})
            views.append({"name": "search_object","UI_layout_num":str(self.current_layout_num),"text": "search_name.text","resource-id": search_object_resourceId,"class": search_object_className,"content-desc": "","xpath": "","instance": ""})
        
        else:
            views.append({"name": "search_object","UI_layout_num":str(self.current_layout_num),"text": self.datatype+"::random","resource-id": search_object_resourceId,"class": search_object_className,"content-desc": "","xpath": "","instance": ""})
        
        results=[]
        preconditions=[{"widget": "e1_widget","relation": "in","UI_layout_num": "0","datatype":""},{"widget": "","relation": "is not empty","UI_layout_num": "","datatype":self.datatype}]
        postconditions=[{"widget": "search_object","relation": "in","UI_layout_num": str(self.current_layout_num),"datatype":""}]

        return results, preconditions, postconditions

    def processView(self, xmllist:list, views:list):
        view_name = input("Please enter the data object you viewed in these steps:")
        view_name_widget=None
        view_object = None
        i=0
        while i<len(xmllist)-1:
            view_name_widget = self.findviewbytext(xmllist[i],view_name,None)
            if view_name_widget!=None:
                view_name_layout = i
                if view_name_widget.resourceId!="":
                    view_name_instance=self.findviewinstance(xmllist[i], view_name_widget.resourceId, None, view_name)
                    view_name_resourceId = view_name_widget.resourceId
                    view_name_className = ""
                elif view_name_widget.className!="":
                    view_name_instance=self.findviewinstance(xmllist[i], None, view_name_widget.className, view_name)
                    view_name_resourceId = ""
                    view_name_className = view_name_widget.className
                else:
                    print("wrong")
                break
            i=i+1
        view_object = self.findviewbytext(xmllist[len(xmllist)-1],view_name,view_name_widget)
        view_object_resourceId = ""
        view_object_className = ""
        if view_object!=None:
            if view_object.resourceId!="":
                view_object_resourceId = view_object.resourceId
            elif view_object.className!="":
                view_object_className = view_object.className
            else:
                print("wrong")
        views.append({"name": "view_name","UI_layout_num": str(view_name_layout),"text": "","resource-id": view_name_resourceId,"class": view_name_className,"content-desc": "","xpath": "","instance": str(view_name_instance)})
        views.append({"name": "view_object","UI_layout_num":str(self.current_layout_num),"text": "view_name.text","resource-id": view_object_resourceId,"class": view_object_className,"content-desc": "","xpath": "","instance": ""})
        results=[]
        preconditions=[{"widget": "e1_widget","relation": "in","UI_layout_num": "0","datatype":""}]
        postconditions=[{"widget": "view_object","relation": "in","UI_layout_num": str(self.current_layout_num),"datatype":""}]

        return results, preconditions, postconditions

    def parseRecoding(self):
        xmllist = self.xmllist
        views = self.views

        #Get and generate additional information

        if self.DMFtype == "add":
            results, preconditions, postconditions = self.processAdd(xmllist, views)
        elif self.DMFtype == "delete":
            results, preconditions, postconditions = self.processDelete(xmllist, views)
        elif self.DMFtype == "edit":
            results, preconditions, postconditions = self.processEdit(xmllist, views)
        elif self.DMFtype == "search":
            results, preconditions, postconditions = self.processSearch(xmllist, views)
        elif self.DMFtype == "view":
            results, preconditions, postconditions = self.processView(xmllist, views)
        
        self.results = results
        self.preconditions = preconditions
        self.postconditions = postconditions


    def addPrecondition(self):
        preconditions = self.postconditions
        views = self.views

        #Generate json file based on information

        while True:
            pre_num = int(input("How many additional preconditions do you want to add:"))
            if pre_num >= 0:
                break

        for pre_index in range(pre_num):
            preconditions.append({"widget": "pre"+str(pre_index)+"_widget","relation": "","UI_layout_num": "0","datatype":""})
            views.append({"name": "pre"+str(pre_index)+"_widget","UI_layout_num":"0","text": "","resource-id": "","class": "","content-desc": "","xpath": "","instance": ""})

        if pre_num >= 1:
            self.preconditions = preconditions
            self.views = views
            print(f"Successfully add {pre_num} Precondition!")

    def save_DMF_JSON(self):
        DMFdata = {"widgets": self.views,"events":self.events,"impacts":self.results,"preconditions":self.preconditions,"name":self.DMFtype+" "+self.datatype, "type":self.DMFtype,"datatype":self.datatype,"post-conditions":self.postconditions,"proportion":"10"}
        self.json = demjson.encode(DMFdata)

        f = open(self.root_path+"/test.json",'w',encoding='utf-8')
        f.write(self.json)
        f.flush()
        f.close()
    
    def mkdirDMFs(self):
        #Create another file
        if not os.path.exists(self.root_path+"keyviews"+self.json_name+".json"):
            f = open(self.root_path+"keyviews"+self.json_name+".json",'w',encoding='utf-8')
            keyviews = {"keyviews": [{"view": "<node NAF=\"#any#\" index=\"#any#\" text=\"#any#\" resource-id=\"inputbyyourself\" class=\"#any#\" package=\"#any#\" content-desc=\"#any#\" checkable=\"#any#\" checked=\"#any#\" clickable=\"#any#\" enabled=\"#any#\" focusable=\"#any#\" focused=\"#any#\" scrollable=\"#any#\" long-clickable=\"#any#\" password=\"#any#\" selected=\"#any#\" visible-to-user=\"#any#\" bounds=\"\" />"},]}
            json = demjson.encode(keyviews)
            f.write(json)
            f.flush()
            f.close()
        if not os.path.exists(self.root_path+"dmf"+self.json_name+".json"):
            f = open(self.root_path+"dmf"+self.json_name+".json",'w',encoding='utf-8')
            dmfList = {"dmfs":[]}
            json = demjson.encode(dmfList)
            f.write(json)
            f.flush()
            f.close()


    def start(self):

        print("Record start")
        self.mkdirTemp()
        self.mkdirDMFs()
        
        # Connect device and initialize
        self.device.connect()
        self.device.install_app(self.app.app_path)
        self.device.use.set_orientation("n")
        # self.device.clear_app(self.app)
        self.device.start_app(self.app)

        #Open the weditor to record the script
        # process = subprocess.Popen(["python3","-m","weditor"])
        # processId = process.pid
        time.sleep(5)

        while True:
            self.recordDMF()
            self.getUiautomatorInst()
            if self.ui_inst_num + 1 == self.screenshot_num:
                break
            else:
                print("ui_instruction_num doesn't match screenshot_num, please try again.")
        
        self.parseRecoding()
        self.addPrecondition()
        self.save_DMF_JSON()
        
        print(f"Successfully record DMF {self.DMFtype}!")