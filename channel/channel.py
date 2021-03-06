from channel import response_message
from db_driver import redis_set_get
from redis_handle import redis_pub_sub


class Channel:
    def __init__(self, room_no):
        self.room_no = room_no
        self.is_connected = False
        self.connection = None
        self.protocol = None
        self._subscription = None
        self.user_id = ""

    async def _connect(self):
        self.connection = await redis_pub_sub.create_connection_pool()
        self.is_connected = True

    async def join_channel(self, app, user_id, user_name):
        if not self.is_connected:
            await self._connect()

        self.user_id = user_id
        message = f'{user_id}님이 입장했습니다.'
        await redis_pub_sub.send_message(self.room_no, message)
        await redis_set_get.set_hash_data(app, self.room_no, user_id, user_name)
        self._subscription = await redis_pub_sub.subscribe_channel(self.connection, self.room_no)

    async def leave_channel(self, app, user_id):
        if not self.is_connected:
            await self._connect()

        message = f'{user_id}님이 나갔습니다.'
        await redis_pub_sub.send_message(self.room_no, message)
        await redis_pub_sub.unsubscibe_channel(self._subscription, self.room_no)
        await redis_set_get.del_hash_keys(app, self.room_no, [user_id])

    async def send_message(self, message):
        if not self.is_connected:
            await self._connect()

        return await redis_pub_sub.send_message(self.room_no, message)

    async def send_message_to_user(self, from_id, message):
        if not self.is_connected:
            await self._connect()

        room_no = str(self.room_no)[:str(self.room_no).find(":")]
        return await redis_pub_sub.send_message(room_no + ":" + from_id, message)

    async def receive_message(self, app, ws):
        if not self.is_connected:
            await self._connect()

        while True:
            try:
                message = await redis_pub_sub.receive_message(self._subscription)
                await ws.send(str(message.value))
            except ConnectionError:
                await redis_pub_sub.unsubscibe_channel(self._subscription, self.room_no)
                await redis_set_get.del_hash_keys(app, self.room_no, [self.user_id])

    async def notify_channel_info(self, app, ws, notify_data_kind):
        if not self.is_connected:
            await self._connect()

        message = ''
        if notify_data_kind is 'room_info':
            user_count = await redis_set_get.get_hash_data_len(app, self.room_no)
            user_list = await redis_set_get.get_hash_all_value(app, self.room_no)
            message = response_message.ResponseMessage.make_room_info(user_count, user_list)

        elif notify_data_kind is 'rooms_lobby_data':
            pass

        # 채팅방 안에서 방 삭제
        elif notify_data_kind is 'room_deleted':
            message = response_message.ResponseMessage.make_deleted_sign(self.room_no)

        elif notify_data_kind is 'data_not_json':
            message = response_message.ResponseMessage.make_alter_sign(self.room_no, 'IS NOT JSON TYPE')

        await ws.send(str(message))
