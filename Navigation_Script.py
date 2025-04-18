#!/usr/bin/env python
import rospy
import actionlib
#import urllib.request
import time
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from actionlib_msgs.msg import GoalStatus
from std_msgs.msg import Int32
from std_msgs.msg import Float32
from Adafruit_IO import MQTTClient

ROBOT_FEED = 'capstone.robot-command'
ROUTE_FEED = 'capstone.robot-route-status'
ADAFRUIT_KEY = 'aio_daAO81fiy6Pux0KLKCoBe1P1MsXz'
ADAFRUIT_USERNAME = '2201164'
#myAPI = '3L62XP8AY5PEKLEY' #Thingspeak API Key
#baseURL = 'https://api.thingspeak.com/update?api_key=%s' % myAPI

robotcommand = 0
loadcellvalue = 0 #Initialize load cell value
ultrasonicvalue = 0 #Initialize ultrasonic value
robotlocation = 1 #Check/counter value, assuming robot starts at situated location
trips = 0
tripduration = 0

#--- Dashboard ---
def message(client, feed_id, payload):
    global  robotcommand
    print(f"Received: {payload} from {feed_id}")
    robotcommand = payload
#    print(type(robotcommand)) #To check variable type
def connected(client):
    print("Connected to dashboard")
    client.subscribe(ROBOT_FEED)

def disconnected(client):
    print("Disconnected from dashboard")
    sys.exit(0)

client = MQTTClient(ADAFRUIT_USERNAME, ADAFRUIT_KEY)
client.on_message = message
client.on_connect    = connected
client.on_disconnect = disconnected
client.connect()
client.loop_background()
client.publish("capstone.trip-duration", 0)
client.publish("capstone.number-of-trips", 0)
client.publish("capstone.robot-route-status", "Robot at original location.")
#--- Navigation ---
def robotNavigation(x, y, z, w):
        client = actionlib.SimpleActionClient('move_base', MoveBaseAction)
        client.wait_for_server()
        rospy.loginfo("Connected to move_base server.")

        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = "map"
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.pose.position.x = x
        goal.target_pose.pose.position.y = y
        goal.target_pose.pose.orientation.z = z
        goal.target_pose.pose.orientation.w = w

        client.send_goal(goal)
        rospy.loginfo("Robot on route.")
        while not rospy.is_shutdown():
            navigationstate = client.get_state()
            if navigationstate == GoalStatus.SUCCEEDED:
                rospy.loginfo("Robot has reached destination.")
                return True
            elif navigationstate == GoalStatus.ABORTED or navigationstate == GoalStatus.REJECTED:
                rospy.logerr("Robot is unable to reach destination.")
                return False
            rospy.sleep(0.1)

#--- Loadcell Node ---
def loadcell_callback(msg):
    global loadcellvalue
    loadcellvalue = msg.data
    rospy.loginfo(f"Received load cell value: {loadcellvalue}")
#--- Ultrasonic Node ---
def ultrasonic_callback(msg):
    global ultrasonicvalue
    ultrasonicvalue = msg.data
    rospy.loginfo(f"Received ultrasonic value: {ultrasonicvalue}")
def startinglocation():
    goal_x = -0.030000116676092148
    goal_y = 0.1300000697374344
    goal_z = 0.9680282113226497
    goal_w = 0.2508413484325729
    # Move to the specified goal
    result = robotNavigation(goal_x, goal_y, goal_z, goal_w)

#--- Main function ---
if __name__ == '__main__':
    try:
        rospy.init_node('navigation_node')
        rospy.loginfo("Navigation Program has started.")
        # Subscribe to the sensor topic for navigation commands
        rospy.Subscriber("loadcellreading", Float32, loadcell_callback)
        rospy.Subscriber("ultrasonicreading", Float32, ultrasonic_callback)
        pub1 = rospy.Publisher("tripduration", Float32, queue_size = 10)
        pub2 = rospy.Publisher("trips", Int32, queue_size = 10)
        pub3 = rospy.Publisher("robotlocation", Int32, queue_size=10)
        # Main loop
        rate = rospy.Rate(1/3)  # 10 Hz
        startinglocation()
        while not rospy.is_shutdown():
            if robotlocation == 1: #if at origin
                if (ultrasonicvalue >=20 and ultrasonicvalue <=26) or (loadcellvalue >=1000) or robotcommand == "1":
                    trips += 1
                    tripstart = time.time()
                    client.publish("capstone.robot-route-status", "Robot on-route for disposal.")
                    goal_x = -1.9799995422363281
                    goal_y = 1.6600000858306885
                    goal_z = 0.42415487959412
                    goal_w = 0.9055896632120408
                    result = robotNavigation(goal_x, goal_y, goal_z, goal_w)
                    if result:
                        robotcommand = 0
                        disposaltimestart = time.time()
                        completedisposal = False
                        #pub1.publish(tripduration)
                        pub2.publish(trips)
                        client.publish("capstone.robot-route-status", "Robot has reached disposal.")
                        client.publish("capstone.number-of-trips", trips)
                        print(f"Disposal trip took: {tripduration} seconds")
                        print(f"Current number of disposal trips: {trips}")
#                        timeurl = baseURL + '&field5=%f' % tripduration
#                        conn = urllib.request.urlopen(timeurl)
#                        conn.close
                        #if trips == 0:
                        #    trips = 1
                        #tripduration = 0
                        robotlocation = 2
                        pub3.publish(robotlocation)
                        rospy.loginfo("Robot has reached disposal")
            elif robotlocation==2: #if at disposal
                if (loadcellvalue <= 100 and ultrasonicvalue <3) and not completedisposal:
                    if disposaltimestart > 0:
                        disposaltime = time.time() - disposaltimestart
                        client.publish("capstone.disposal-duration", disposaltime)
                    client.publish("capstone.robot-route-status", "Robot on-route to original location.")
                    startinglocation()
                    if result:
                        tripduration = time.time() - tripstart
                        client.publish("capstone.trip-duration", tripduration)
                        robotlocation = 1
                        pub3.publish(robotlocation)
                        client.publish("capstone.robot-route-status", "Robot returned to original location.")
                        rospy.loginfo("Robot returned to original location")
            rate.sleep()

    except rospy.ROSInterruptException:
        rospy.loginfo("Node shutting down.")
