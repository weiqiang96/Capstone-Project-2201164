
import RPi.GPIO as GPIO
import urllib.request
import time
import rospy
import paho.mqtt.client as paho
from std_msgs.msg import Int32, Float32
from hx711 import HX711

#---Setup---#
GPIO.setmode(GPIO.BCM)
TRIG1 = 4   # Trigger pin for Sensor 1
ECHO1 = 17  # Echo pin for Sensor 1
TRIG2 = 20  # Trigger pin for Sensor 2
ECHO2 = 16  # Echo pin for Sensor 2
TRIG3 = 19
ECHO3 = 26
IR = 12

hx = HX711(dout_pin=22, pd_sck_pin=27)
hx.zero()
ratio = 109.5
hx.set_scale_ratio(ratio)

GPIO.setup(TRIG1, GPIO.OUT)
GPIO.setup(ECHO1, GPIO.IN)
GPIO.setup(TRIG2, GPIO.OUT)
GPIO.setup(ECHO2, GPIO.IN)
GPIO.setup(TRIG3, GPIO.OUT)
GPIO.setup(ECHO3, GPIO.IN)
GPIO.setup(IR, GPIO.IN)

#---MQTT---#
AIO_BROKER = "io.adafruit.com"
PORT = 1883
FILL_LEVEL = "capstone.fill-level"
WASTE_LEVEL = "capstone.waste-level"
WASTE_WEIGHT = "capstone.waste-weight"
DISPOSAL_TRIPS = "capstone.number-of-trips"
TRIP_DURATION = "capstone.trip-duration"
AIO_USERNAME = "2201164"
AIO_KEY = "aio_daAO81fiy6Pux0KLKCoBe1P1MsXz"

#---RESTAPI---#
#AIO_BASEURL = f"https://io.adafruit.com/api/v2/{AIO_USERNAME}/feeds"
#myAPI = '3L62XP8AY5PEKLEY'
#baseURL = 'https://api.thingspeak.com/update?api_key=%s' % myAPI

trips = 0
tripduration = 0
# Ensure Trigger is initially set to False
#GPIO.output(TRIG, False)

#---MQTT FUNCTIONS---#
def connected(client, userdata, flags, rc):
      print("Connected to dashboard")

client = paho.Client()
client.on_connect = connected
client.username_pw_set(AIO_USERNAME, AIO_KEY)
client.connect('io.adafruit.com',1883)
client.loop_start()

#---ROS SUBSCRIBERS---#
def duration_callback(msg):
      global tripduration
      tripduration = msg.data
      rospy.loginfo(f"Trip duration: {tripduration}")
def trips_callback(msg):
      global trips
      trips = msg.data
      rospy.loginfo(f"Number of trips: {trips}")

#---ULTRASONIC---#
def ultrasonic(TRIG, ECHO):
          GPIO.output(TRIG, False)
          time.sleep(0.000002)
          GPIO.output(TRIG, True)
          time.sleep(0.00001)  # Send a pulse for 10 microseco>
          GPIO.output(TRIG, False)

          # Measure the time it takes for the Echo to return
          while GPIO.input(ECHO) == 0:
              pulse_start = time.time()

          while GPIO.input(ECHO) == 1:
              pulse_end = time.time()

          pulse_duration = pulse_end - pulse_start
          distance = round(pulse_duration * 17150,2)  # Convert to cent>
#            distance = 30 - distance
          if distance < 0:
              distance = abs(distance)
          return distance

#---LOADCELL---#
def loadcell():
          weight = hx.get_weight_mean()
          weight = round(weight,2)
          if weight < 0:
              weight = 0
          return weight

#---MAIN---#
def talker():
      ultrasonicpub = rospy.Publisher('ultrasonicreading', Float32, queue_size=10)
      loadcellpub = rospy.Publisher('loadcellreading', Float32, queue_size=10)
      rospy.init_node('sensornode')
      rospy.Subscriber("tripduration", Float32, duration_callback)
      rospy.Subscriber("trips", Int32, trips_callback)
      rate = rospy.Rate(1/10)
      previousdistance = 0
      distance1 = ultrasonic(TRIG1, ECHO1)
      time.sleep(1)
      distance2 = ultrasonic(TRIG2, ECHO2)
      time.sleep(1)
      distance3 = ultrasonic(TRIG3, ECHO3)
      time.sleep(1)
      distance = 30 - round((distance1+distance2+distance3)/3,0)
      prevdistance1 = distance1
      prevdistance2 = distance2
      prevdistance3 = distance3
      while not rospy.is_shutdown():
          if (GPIO.input(IR)==0):
              print("Bin is closed")
              distance1 = ultrasonic(TRIG1, ECHO1)
              time.sleep(1)
              distance2 = ultrasonic(TRIG2, ECHO2)
              time.sleep(1)
              distance3 = ultrasonic(TRIG3, ECHO3)
              prevdistance1 = distance1
              prevdistance2 = distance2
              prevdistance3 = distance3
          else:
              print("Bin opened")
              distance1 = prevdistance1
              distance2 = prevdistance2
              distance3 = prevdistance3
          distance = 30 - round((distance1+distance2+distance3)/3,0)
          weight = loadcell()
          if distance == 0:
              client.publish('{0}/feeds/{1}'.format(AIO_USERNAME, FILL_LEVEL), 0)
          elif distance > 0 and distance <=3:
              client.publish('{0}/feeds/{1}'.format(AIO_USERNAME, FILL_LEVEL), 10)
          elif distance >3 and distance <= 7:
              client.publish('{0}/feeds/{1}'.format(AIO_USERNAME, FILL_LEVEL), 25)
          elif distance >7 and distance <= 14:
              client.publish('{0}/feeds/{1}'.format(AIO_USERNAME, FILL_LEVEL), 50)
          elif distance >14 and distance <= 22:
              client.publish('{0}/feeds/{1}'.format(AIO_USERNAME, FILL_LEVEL), 75)
          elif distance >22 and distance <= 26:
              client.publish('{0}/feeds/{1}'.format(AIO_USERNAME, FILL_LEVEL), 90)

         # if  distance > 1 or distance == 0:
         #      previousdistance = distance
         # if distance < previousdistance:
         #      distance = previousdistance
          rospy.loginfo(f"Distance1: {distance1}cm")
          rospy.loginfo(f"Distance2: {distance2}cm")
          rospy.loginfo(f"Distance3: {distance3}cm")

          rospy.loginfo(f"Distance: {distance} cm")
          rospy.loginfo(f"Weight: {weight} g")
#           - MQTT-
          client.publish('{0}/feeds/{1}'.format(AIO_USERNAME, WASTE_LEVEL), distance)
          client.publish('{0}/feeds/{1}'.format(AIO_USERNAME, WASTE_WEIGHT), weight)
#           - RESTAPI-
#            url = f"{baseURL}&field1={distance}&field2={weight}&field4={trips}&field5={tripduration>

#            print(f"Sending ultrasonic distance to ThingSpeak: {url}")
#            try:
#                conn = urllib.request.urlopen(url)
#                conn.close()
#                if trips and tripduration > 0:
#                   trips = 0
#                   tripduration = 0
#                print("Data sent.")
#            except Exception as e:
#                print(f"Error sending data: {e}")
          ultrasonicpub.publish(distance)
          loadcellpub.publish(weight)
          rate.sleep()

if __name__ == '__main__':
  try:
      talker()
  except rospy.ROSInterruptException:
      pass
  finally:
      GPIO.cleanup()
      rospy.loginfo("Program terminated")
