#!/usr/bin/python
import cgi
import cgitb
import urllib
import json
import socket, time
from itertools import izip_longest
from requests_futures.sessions import FuturesSession

cgitb.enable()
session = FuturesSession(max_workers=10)

# choose a sane default config
config = {
  "areas" : [
    {
      "shortName" : "1",
      "longName" : "Main",
      "takesAVInputs" : False
    }
  ],
  "inputs" : [{"systemName":"Off"}],
  "inputPrefs" : {
    "ignoreUnnamedPrimary" : False,
    "ignoreSupplemental" : []
  }
}

# load the config if available
CONFIG_LOCATION = "genpage.json"
try:
    config = json.load(open(CONFIG_LOCATION))
except:
    pass

# utility functions
def grouper(n, iterable, fillvalue=None):
    args = [iter(iterable)] * n
    return izip_longest(fillvalue=fillvalue, *args)

# device control functions
BUFFER_SIZE = 8192
def sendRawMessage(address, port, command):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    try:
        s.connect((address, port))
        s.send(command)
        time.sleep(0.03)
        data = s.recv(BUFFER_SIZE)
        s.close
        return data.rstrip()
    except socket.timeout as msg:
        raise Exception("No connection to " + address)

def sendReceiverMessage(unit, command, arguments):
    msg = unit + ":" + command + "=" + arguments
    msg +=  "\r\n"
    return sendRawMessage(config["receiver"]["address"], config["receiver"]["port"], msg)

def sendTvMessage(area, command):
    if "tv" not in area:
        return ""
    if area["tv"]["type"] != "ip_serial":
        return ""
    #return sendRawMessage(area["tv"]["address"], area["tv"]["port"], command)

def getReceiverInputState(area):
    return sendReceiverMessage("@"+area["avZone"], "INP", "?").split("=")[1]

def setReceiverInputState(area, avInput):
    sendReceiverMessage("@"+area["avZone"], "INP", avInput)

def getReceiverPowerState(area):
    states = {
        "On" : "On",
        "Standby" : "Off"
    }
    return states[sendReceiverMessage("@"+area["avZone"], "PWR", "?").split("=")[1]]
    
def setReceiverPowerState(area, avPower):
    states = {
        "On" : "On",
        "Off" : "Standby"
    }
    sendReceiverMessage("@"+area["avZone"], "PWR", states[avPower])

def setTvPowerState(area, tvPower):
    sendTvMessage(area, area["tv"][tvPower])
    
def setPowerStates(area, currentState, selectedState):
    if currentState != selectedState:
        setReceiverPowerState(area, selectedState)
        setTvPowerState(area, selectedState)

def setInput(area, selectedInput, currentInput, pwrState):
    if selectedInput == "Off":
        setPowerStates(area, pwrState, "Off")
        return

    setPowerStates(area, pwrState, "On")
    if currentInput != selectedInput:
        setReceiverInputState(area, selectedInput)

def activateState(control, newState):
    if "mechanism" not in control:
        return
    if control["mechanism"] == "rest":
        [session.post(u, data=json.dumps(newState["payload"]), timeout=1) for u in control["targets"]]

# page-related functions
def getControlArea(shortName):
    return [area for area in config["areas"] if area["shortName"] == shortName][0]

def genClickableTD(backgroundColor, width, link, contents, textcolor="#000000"):
    staticStyles = "cursor: pointer; cursor: hand; padding: 20px;"
    style = "%s background-color: %s; color: %s;" % (staticStyles, backgroundColor, textcolor)
    onClick = "window.location=\"%s\"" % link
    attributes = "align='center' style='%s' width='%d%%' onclick='%s'" \
        % (style, width, onClick)
    return "<td %s>%s</td>" % (attributes, contents)

# input enumeration
# These inputs are possible inputs that can be pushed out any zone, but are
# not enumerated like normal inputs since they're more like apps.
suppInputs = {
    "BT" : {
        "systemName" : "Bluetooth",
    },
    "TUN" : {
        "systemName" : "TUNER",
        "userName" : "Radio"
    },
    "RHAP" : {
        "systemName" : "Rhapsody",
    },
    "SIRIUSXM" : {
        "systemName" : "SiriusXM",
    },
    "SPOTIFY" : {
        "systemName" : "Spotify",
    },
    "PANDORA" : {
        "systemName" : "Pandora",
    },
    "AIRPLAY" : {
        "systemName" : "AirPlay",
    },
}

def enumerateReceiverInputs():
    coreInputs = []
    # get list of "normal" inputs
    for avInput in sendReceiverMessage("@SYS", "INPNAME", "?").splitlines(False):
        # strip off @SYS:
        avInput = avInput.split(":")[1].split("=")
        inputId = avInput[0][len("INPNAME"):]
        inputName = avInput[1]
        # ignore inputs that haven't been renamed
        if config.get("inputPrefs", {}).get("ignoreUnnamedPrimary", False) and inputId[-3:] == inputName[-3:]:
            continue
        coreInputs.append({"systemName" : inputId, "userName" : inputName})

    # probe for supplementary inputs
    for suppInput in suppInputs.keys():
        # check to see if this input is ignored
        ignored = [supp for supp in config.get("inputPrefs", {}).get("ignoreSupplemental", []) if supp == suppInputs[suppInput]["systemName"]]
        if not len(ignored) and sendReceiverMessage("@"+suppInput, "AVAIL", "?") != "@UNDEFINED":
            coreInputs.append(suppInputs[suppInput])

    # add "Off" input
    coreInputs.append({"systemName":"Off"})
    return coreInputs

# body generation
form = cgi.FieldStorage()
zone = form.getvalue("zone", "1")
refresh = form.getvalue("refreshInputs","0")
selectedArea = getControlArea(zone)
try:
    if refresh == "1":
        newInputs = enumerateReceiverInputs()
        config["inputs"] = newInputs
        json.dump(config, open(CONFIG_LOCATION, 'w'), sort_keys=True, indent=2)
    currentInput = getReceiverInputState(selectedArea)
    currentPower = getReceiverPowerState(selectedArea)
    inputSelection = form.getvalue("input", "")
    if (inputSelection != ""):
        # change inputs for the current zone
        try:
            setInput(selectedArea, inputSelection, currentInput, currentPower)
        except:
            pass
        if inputSelection == "Off":
            currentPower = "Off"
        else:
            currentInput = inputSelection
            currentPower = "On"
except:
    currentInput = "Off"
    currentPower = "Off"


#print "content-type: text/html\n"

print "<!DOCTYPE html>"
print "<html><head>"
print "<title>%s</title>" % selectedArea['longName']
print "</head><body>"
print "<table height='100%' width='100%' style='background-color: #cccccc' cellspacing='0'>"
print "<tr>"
print "<td align='center' style='top-padding:10px'></td>"
print "<td align='center' style='top-padding:10px'><h1>Home Control</h1></td>"
print "<td align='right' style='top-padding:10px' valign='center'><a href='?refreshInputs=1&zone=%s'><img src='/refresh.png' style='width:15%%;height:auto;'/></a></td>" % zone
print "</tr>"
print "<tr>"

# Create a column for each control area
for area in config["areas"]:
    background = "#ffffff"
    if area == selectedArea:
        background = "#cccccc"
    print genClickableTD(background, 100/len(config["areas"]),
        "?zone=%s" % (area["shortName"]), area["longName"])

print "</tr>"
print "<tr height='100%' style='background-color: #cccccc'>"
print "<td colspan='%s' style='padding: 10px' valign='top'>" % len(config["areas"])
print "<table width='100%'>"
# list shared A/V inputs
# Future improvement: Support houses with multiple receivers
if selectedArea["takesAVInputs"]:
    print "<tr>" 
    print "<td align='center' style='background-color: #cccccc; padding: 10px' colspan='3'>A/V Inputs</td>"
    print "</tr>" 
    for input1, input2, input3 in grouper(3, config["inputs"]):
        print "<tr>" 
        for avInput in [input1, input2, input3]:
            if avInput == None:
                print "<td></td>"
                continue
            userName = ""
            systemName = ""
            if "systemName" in avInput:
                systemName = avInput["systemName"]
            if "userName" in avInput:
                userName = avInput["userName"]
            else:
                userName = systemName

            # if "Off", highlight "Off" and lowlight the last-selected input
            bgcolor = "#ffffff"
            if currentInput == systemName:
                if currentPower == "On":
                    bgcolor = "#00ff00"
                else:
                    bgcolor = "#009900"
            if currentPower != "On" and systemName == "Off":
                bgcolor = "#00ff00"
            
            print genClickableTD(bgcolor, 33,
                "?zone=%s&input=%s" % (selectedArea["shortName"], systemName),
                userName)
        print "</tr>" 
if "controls" in selectedArea:
    print "<tr>" 
    print "<td align='center' style='background-color: #cccccc; padding: 10px' colspan='3'>Controls</td>"
    print "</tr>"
    for control1, control2, control3 in grouper(3, selectedArea["controls"]):
        header = ""
        indicator = ""
        for control in [control1, control2, control3]:
            if control == None:
                header += "<td></td>"
                indicator += "<td></td>"
                continue
            # XXX get current state
            state = form.getvalue(control["id"], "")
            if state == "" or state == "True":
                state = True
            if state == "False":
                state = False
            stateMap = [
                {
                    "key" : True,
                    "text" : "On",
                    "color" : "#00ff00",
                },
                {
                    "key" : False,
                    "text" : "Off",
                    "color" : "#ffffff",
                },
            ]
            stateData = control.get("indicatorMap", stateMap)
            states = [stateEntry for stateEntry in stateData if stateEntry["key"] == state]
            if len(states):
                state = states[0]
            else:
                state = stateData[0]
            nextState = state
            try:
                stateIndex = (stateData.index(state) + 1) % len(stateData)
                nextState = stateData[stateIndex]
            except ValueError:
                nextState = stateData[0]
            url = "?%s" % urllib.urlencode({ "zone" : zone, control["id"] : str(nextState["key"])})
            header += genClickableTD("#cccccc", 33, url, control["name"])
            textcolor = "#000000"
            if "textcolor" in state:
                textcolor = state["textcolor"]
            indicator += genClickableTD(state["color"], 33, url, state["text"], textcolor)
            activateState(control, state)
        print "<tr>" 
        print header
        print "</tr>" 
        print "<tr>" 
        print indicator
        print "</tr>" 
print "</table>"
#print cgi.escape(form.getvalue("message", "default_value"))
print "</td></tr>"
print "</table>"
print "</body></html>"
session.close()
