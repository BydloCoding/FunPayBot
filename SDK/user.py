from .keyboard import Keyboard
import vk_api


class User(object):
    # method to insert keyword map
    user_id_methods = {
        "messages.getHistory": "user_id", "users.get": "user_ids"}

    def __new__(cls, vk, user_id, method=None):
        try:
            get = vk.users.get(user_ids=user_id, fields="photo_id")[0]
            instance = super(User, cls).__new__(cls)
            instance.request = get
            instance.avatar = f"photo{get['photo_id']}" if get.get(
                'photo_id') is not None else ""
            instance.user_name = f"{get['first_name']} {get['last_name']}"
            return instance
        except:
            return None

    def __init__(self, vk, user_id, method=None):
        self._vk = vk
        self._method = method
        self.id = user_id

    def write(self, message, keyboard=None, **kwargs):
        if keyboard is not None:
            kwargs["keyboard"] = Keyboard.byKeyboard(keyboard)
        try:
            return self._vk.messages.send(user_id=self.id, message=message, random_id=vk_api.utils.get_random_id(),
                                          **kwargs)
        except:
            return

    def __getattr__(self, method):  # str8 up
        if '_' in method:
            m = method.split('_')
            method = m[0] + ''.join(i.title() for i in m[1:])
        return User(
            self._vk,
            self.id,
            (self._method + '.' if self._method else '') + method
        )

    def __call__(self, **kwargs):
        if self._method in User.user_id_methods:
            kwargs[User.user_id_methods[self._method]] = self.id
        self._vk._method = self._method
        tmpReturn = self._vk.__call__(**kwargs)
        # set to null
        self._vk._method = None
        self._method = None
        return tmpReturn
