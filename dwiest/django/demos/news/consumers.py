import asyncio
import json
from channels.consumer import AsyncConsumer
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from random import randint
from time import sleep
from .models import NewsItem
#from channels.layers import get_channel_layer
from asgiref.sync import sync_to_async

class NewsFeed(AsyncJsonWebsocketConsumer):

    @sync_to_async
    def getNewsItems(self):
#      return list(NewsItem.objects.all())
      return list(NewsItem.objects.filter(status=0))

    def __init__(self):
      print("NewsFeed()")
#      self.news = ["uhnce","tice","fee times","a mady"]


    async def websocket_connect(self, event):
        print("websocket connected", event)
#        sync_to_async(NewsItem.objects.get)()
#        await self.channel_layer.group_add('woot',self.channel_name)
        self.news = await self.getNewsItems()
        self.generator = await self.next_index()
        await self.accept()
#        await self.channel_layer.group_send('woot',{'type':'foo.msg','content':'0'})


    async def websocket_disconnect(self, event):
        print("disconnecting", event)
#        await self.channel_layer.group_discard('woot',self.channel_name)
        print("disconnected")


    async def websocket_receive(self, event):
        print("websocket_receive", event)
        #sleep(3)
      #  await self.channel_layer.send("woot",{"type":"foo.msg","content":str(randint(0,100))})
        i = next(self.generator)

        #await self.send(text_data=str(self.news[i]))
        await self.send(text_data=str(self.news[i].description))

    @sync_to_async
    def next_index(self):
      n = len(self.news)
      i = 0
      while True:
        yield i
        i = (i+1)%n

