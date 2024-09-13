# actions.py

from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import mysql.connector
from gtts import gTTS
import os

class ActionCallTicket(Action):
    def name(self) -> Text:
        return "action_call_ticket"

    def connect_to_db(self):
        # Database connection details
        try:
            connection = mysql.connector.connect(
                host="localhost",  # Update if needed
                user="root",  # Your MySQL username
                password="",  # Your MySQL password
                database="hospital_queue"  # The database you created
            )
            return connection
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            return None

    def fetch_queue_data(self):
        # Query the 'queues' table for the next ticket
        connection = self.connect_to_db()
        if connection is None:
            return None
        
        cursor = connection.cursor(dictionary=True)
        query = "SELECT ticket_number, room_number FROM queue ORDER BY ticket_number LIMIT 1"
        cursor.execute(query)
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()

        return result
    
    def announce_ticket(self, ticket_number: int, room_number: str):
        # Text to announce
        text_to_say = f"Ticket number {ticket_number}, please proceed to {room_number}."
        
        # Convert the text to speech using gTTS
        tts = gTTS(text=text_to_say, lang='en')
        tts.save("ticket_announcement.mp3")
        
        # Play the saved audio file
        os.system("start ticket_announcement.mp3")  # For Windows. Use "afplay" on macOS, "mpg123" on Linux.
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Fetch ticket data from the database
        ticket_data = self.fetch_queue_data()
        
        if ticket_data:
            ticket_number = ticket_data['ticket_number']
            room_number = ticket_data['room_number']
            
            # Announce the ticket
            self.announce_ticket(ticket_number, room_number)
            
            dispatcher.utter_message(text=f"Calling ticket number {ticket_number} to {room_number}.")
        else:
            dispatcher.utter_message(text="No tickets available at the moment.")
        
        return []
