# import the necessary packagesfo YOLO
import numpy as np
import argparse
import imutils
import time
import cv2
import os
import webbrowser

#Mail related imports
import smtplib
from string import Template
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

#location related imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
import time

MY_ADDRESS = 'chandanakandagatla1@gmail.com'
PASSWORD = 'kcmvp@2622'

def get_contacts(filename):
    """
    Return two lists names, emails containing names and email addresses
    read from a file specified by filename.
    """
    
    names = []
    emails = []
    with open(filename, mode='r', encoding='utf-8') as contacts_file:
        for a_contact in contacts_file:
            names.append(a_contact.split()[0])
            emails.append(a_contact.split()[1])
    return names, emails
	
def sendMail(mapString):
	print(mapString)
	names, emails = get_contacts('myContacts.txt') 
	
	# set up the SMTP server
	s = smtplib.SMTP(host='smtp.gmail.com', port=587)
	s.starttls()
	s.login(MY_ADDRESS, PASSWORD)

	# For each contact, send the email:
	for name, email in zip(names, emails):
		msg = MIMEMultipart()       # create a message

		# setup the parameters of the message
		msg['From']=MY_ADDRESS
		msg['To']=email
		msg['Subject']="URGENT: People Gathering Alert"

		# Create the body of the message (a plain-text and an HTML version).
		# link = '<a href="{0}">{1}</a>'.format(destination, description)
		html = """\
            <html>
              <head></head>
              <body>
                <p>Heyy!!!<br>
                   Here is the link <a href="{str1}">Open Map Link</a>
                </p>
              </body>
            </html>
            """.format(str1 = mapString)

        # Record the MIME types of both parts - text/plain and text/html.
		part1 = MIMEText(html, 'html')

        # Attach parts into message container.
        # According to RFC 2046, the last part of a multipart message, in this case
        # the HTML message, is best and preferred.
		msg.attach(part1)
        
        # send the message via the server set up earlier.
		s.send_message(msg)
		del msg
        
    # Terminate the SMTP session and close the connection
	s.quit()
	
def getLocation():
    options = Options()
    options.add_argument("--use-fake-ui-for-media-stream")
    timeout = 30
    driver = webdriver.Chrome(executable_path = './chromedriver.exe', chrome_options=options)
    driver.get("https://mycurrentlocation.net/")
    wait = WebDriverWait(driver, timeout)
    time.sleep(3)
    longitude = driver.find_elements_by_xpath('//*[@id="longitude"]')
    longitude = [x.text for x in longitude]
    longitude = str(longitude[0])
    latitude = driver.find_elements_by_xpath('//*[@id="latitude"]')
    latitude = [x.text for x in latitude]
    latitude = str(latitude[0])
    #accuracy = driver.find_elements_by_xpath('//*[@id="accuracy"]/strong')
    #accuracy = [x.text for x in accuracy]
    #accuracy = str(accuracy[0])
    driver.quit()
    return (latitude,longitude) #,accuracy)

# construct the argument parse and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-i", "--input", required=True,
	help="path to input video")
ap.add_argument("-o", "--output", required=True,
	help="path to output video")
ap.add_argument("-y", "--yolo", required=True,
	help="base path to YOLO directory")
ap.add_argument("-c", "--confidence", type=float, default=0.5,
	help="minimum probability to filter weak detections")
ap.add_argument("-t", "--threshold", type=float, default=0.3,
	help="threshold when applyong non-maxima suppression")
args = vars(ap.parse_args())


# load the COCO class labels our YOLO model was trained on
labelsPath = os.path.sep.join([args["yolo"], "coco.names"])
LABELS = open(labelsPath).read().strip().split("\n")

# initialize a list of colors to represent each possible class label
np.random.seed(42)
COLORS = np.random.randint(0, 255, size=(len(LABELS), 3),
	dtype="uint8")
	
# derive the paths to the YOLO weights and model configuration
weightsPath = os.path.sep.join([args["yolo"], "yolov3.weights"])
configPath = os.path.sep.join([args["yolo"], "yolov3.cfg"])

# load our YOLO object detector trained on COCO dataset (80 classes)
# and determine only the *output* layer names that we need from YOLO
print("[INFO] loading YOLO from disk...")
net = cv2.dnn.readNetFromDarknet(configPath, weightsPath)
ln = net.getLayerNames()
ln = [ln[i[0] - 1] for i in net.getUnconnectedOutLayers()]

# initialize the video stream, pointer to output video file, and
# frame dimensions
vs = cv2.VideoCapture(args["input"])
writer = None
(W, H) = (None, None)

#initialize the counter
peopleCounter = 0
frameCounter = 0
threshold = 5


# try to determine the total number of frames in the video file
try:
	prop = cv2.cv.CV_CAP_PROP_FRAME_COUNT if imutils.is_cv2() \
		else cv2.CAP_PROP_FRAME_COUNT
	total = int(vs.get(prop))
	print("[INFO] {} total frames in video".format(total))
	
# an error occurred while trying to determine the total
# number of frames in the video file
except:
	print("[INFO] could not determine # of frames in video")
	print("[INFO] no approx. completion time can be provided")
	total = -1
	
# loop over frames from the video file stream
while True:
	# read the next frame from the file
	(grabbed, frame) = vs.read()
	
	# if the frame was not grabbed, then we have reached the end
	# of the stream
	if not grabbed:
		break
		
	# if the frame dimensions are empty, grab them
	if W is None or H is None:
		(H, W) = frame.shape[:2]
		
	# construct a blob from the input frame and then perform a forward
	# pass of the YOLO object detector, giving us our bounding boxes
	# and associated probabilities
	blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (416, 416),
		swapRB=True, crop=False)
	net.setInput(blob)
	start = time.time()
	layerOutputs = net.forward(ln)
	end = time.time()
	# initialize our lists of detected bounding boxes, confidences,
	# and class IDs, respectively
	
	boxes = []
	confidences = []
	classIDs = []
	
	# loop over each of the layer outputs
	for output in layerOutputs:
		# loop over each of the detections
		for detection in output:
			# extract the class ID and confidence (i.e., probability)
			# of the current object detection
			scores = detection[5:]
			classID = np.argmax(scores)
			confidence = scores[classID]
			
			# filter out weak predictions by ensuring the detected
			# probability is greater than the minimum probability
			if confidence > args["confidence"]:
				# scale the bounding box coordinates back relative to
				# the size of the image, keeping in mind that YOLO
				# actually returns the center (x, y)-coordinates of
				# the bounding box followed by the boxes' width and
				# height
				box = detection[0:4] * np.array([W, H, W, H])
				(centerX, centerY, width, height) = box.astype("int")
				
				# use the center (x, y)-coordinates to derive the top
				# and and left corner of the bounding box
				x = int(centerX - (width / 2))
				y = int(centerY - (height / 2))
				
				# update our list of bounding box coordinates,
				# confidences, and class IDs
				boxes.append([x, y, int(width), int(height)])
				confidences.append(float(confidence))
				classIDs.append(classID)
				
	# apply non-maxima suppression to suppress weak, overlapping
	# bounding boxes
	idxs = cv2.dnn.NMSBoxes(boxes, confidences, args["confidence"], args["threshold"])
	
	
	# ensure at least one detection exists
	if len(idxs) > 0:
		# loop over the indexes we are keeping
		peopleCounter = 0
		for i in idxs.flatten():
			# extract the bounding box coordinates
			(x, y) = (boxes[i][0], boxes[i][1])
			(w, h) = (boxes[i][2], boxes[i][3])
			# draw a bounding box rectangle and label on the frame
			color = [int(c) for c in COLORS[classIDs[i]]]
			cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
			text = "{}: {:.4f}".format(LABELS[classIDs[i]],
				confidences[i])
			cv2.putText(frame, text, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
			peopleCounter +=1
	
	if peopleCounter > threshold:
		frameCounter +=1
		if frameCounter == 4:
			break
	elif frameCounter > 0:
		frameCounter -= 1
	
	# write number of people in bottom corner
	text = "Persons: {}".format(peopleCounter)
	cv2.putText(frame, text, (10, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 2)			
	
	# check if the video writer is None
	if writer is None:
		# initialize our video writer
		fourcc = cv2.VideoWriter_fourcc(*"MPEG")
		writer = cv2.VideoWriter(args["output"], fourcc, 30,
			(frame.shape[1], frame.shape[0]), True)
			
		# some information on processing single frame
		if total > 0:
			elap = (end - start)
			print("[INFO] single frame took {:.4f} seconds".format(elap))
			print("[INFO] estimated total time to finish: {:.4f}".format(
				elap * total))
				
	# write the output frame to disk
	writer.write(frame)
	
print("[INFO] No. of People: ", peopleCounter)
if peopleCounter > threshold:
	lat, long = getLocation()
	mapString = "https://www.google.com/maps/place/" + lat + "," + long
	webbrowser.open(mapString,new=2)
	sendMail(mapString)
	print(lat, long)
# release the file pointers
print("[INFO] cleaning up...")
writer.release()
vs.release()
