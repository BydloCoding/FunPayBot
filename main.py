
from SDK.listExtension import ListExtension
import re
from time import sleep
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from SDK.stringExtension import StringExtension
from SDK.thread import Thread
from SDK import (database, jsonExtension, user, imports, cmd)

config = jsonExtension.load("config.json")


class LongPoll(VkLongPoll):
    def __init__(self, instance, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance

    def listen(self):
        while True:
            try:
                self.instance.check_tasks()
                updates = self.check()
                for event in updates:
                    yield event
            except:
                # we shall participate in large amount of tomfoolery
                pass


class FunPay(Thread):
    def __init__(self, bot_class, **kwargs) -> None:
        self.bot_class = bot_class
        self.driver = webdriver.Firefox()
        self.replies = jsonExtension.load("data/replies.json", indent=4)
        self.responses = jsonExtension.load("data/responses.json")
        self.purchases = jsonExtension.load("data/purchases.json")
        self.user_login = None
        self.auth()
        super().__init__(**kwargs)

    def auth(self):
        self.driver.get("https://funpay.ru")
        self.driver.find_element(By.CSS_SELECTOR, "a.vk").click()
        self.driver.find_element(By.NAME, "email").send_keys(
            self.bot_class.config["vk_login"])
        self.driver.find_element(By.NAME, "pass").send_keys(
            self.bot_class.config["vk_password"])
        self.driver.find_element(
            By.CSS_SELECTOR, "button.flat_button.oauth_button.button_wide").click()

    def attempt_find_element(self, fr, by, j):
        try:
            return fr.find_element(by, j)
        except NoSuchElementException:
            return

    def attempt_find_elements(self, fr, by, j):
        try:
            return fr.find_elements(by, j)
        except NoSuchElementException:
            return

    def reply(self, message):
        reply_field = self.driver.find_element(By.CSS_SELECTOR, "textarea.form-control")
        reply_field.send_keys(message)
        self.driver.find_element(By.CSS_SELECTOR, "button.btn.btn-gray.btn-round").click()


    def run(self):
        while True:
            self.driver.get("https://funpay.ru/chat/")
            if self.user_login is None:
                self.user_login = self.driver.find_element(
                    By.CSS_SELECTOR, "div.user-link-name").get_attribute("textContent")


            # получить все чаты
            nodes = [node.get_attribute('data-id') for node in self.driver.find_element(
                By.CSS_SELECTOR, "div.contact-list.custom-scroll").find_elements(By.CSS_SELECTOR, "a")]
            for node in nodes:
                self.driver.get(f"https://funpay.ru/chat/?node={node}")
                looking_for = self.driver.find_element(
                    By.CSS_SELECTOR, "div.param-item.chat-panel")
                if "hidden" not in looking_for.get_attribute("className"):
                    element = looking_for.find_element(By.CSS_SELECTOR, "a")
                    string = f"{node}:"
                    string += re.findall(r'\d+',
                                         element.get_attribute('href'))[0]
                    if element.text in self.replies and string not in self.responses:
                        if not self.replies[element.text]["active"]:
                            return
                        self.reply(self.replies[element.text]['first_reply'])
                        self.responses.append(string)


                # сохранение истории сообщений
                user_login = self.driver.find_element(By.CSS_SELECTOR, "div.media.media-user").find_element(By.CSS_SELECTOR, "div.media-user-name").find_element(By.TAG_NAME, "a").text
                messages_file = jsonExtension.loadAdvanced(f"data/messages/{user_login}_{node}.json", content="[]", ident=4)
                messages = self.driver.find_elements(By.CSS_SELECTOR, "div.chat-message")
                last_user_name = ""
                last_date = ""
                for message in messages:
                    user_name = getattr(self.attempt_find_element(message, By.TAG_NAME, "a"), "text", None) or last_user_name
                    last_user_name = user_name
                    date = getattr(self.attempt_find_element(message, By.CSS_SELECTOR, "div.chat-message-date"), "text", None) or last_date
                    last_date = date
                    message_text = message.find_element(By.CSS_SELECTOR, "div.message-text").text
                    d = {
                        "text": message_text,
                        "author": user_name,
                        "date": date
                    }
                    if d not in messages_file:
                        messages_file.append(d)


                # выдача товара
                alerts = self.attempt_find_elements(
                    self.driver, By.CSS_SELECTOR, "div.alert.alert-with-icon.alert-info")
                for alert in alerts:
                    if f"{self.user_login}, не забудьте потом нажать кнопку «Подтвердить выполнение заказа»." not in alert.text and "оплатил" in alert.text:
                        # extract uppercase letters from order url
                        order_id = ''.join(re.findall('[A-Z]+', alert.find_elements("a")[1].get_attribute("href")))
                        # unique string (don't give product to person two times)
                        string = f"{node}:{order_id}"
                        if string not in self.purchases:
                            for product in list(self.replies):
                                if not self.replies[product]["active"]:
                                    return
                                if product in alert.text:
                                    self.reply(self.replies[product]['product'])
                                    self.replies[product]["active"] = False
                                    self.purchases.append(string)
                                    break

            sleep(30)


class MainThread(Thread):
    def run(self):
        self.config = config
        imports.ImportTools(["packages", "Structs"])
        self.database = database.Database(
            config["db_file"], config["db_backups_folder"], self)
        self.db = self.database
        database.db = self.database
        self.vk_session = vk_api.VkApi(token=self.config["vk_api_key"])
        self.longpoll = LongPoll(self, self.vk_session)
        self.vk = self.vk_session.get_api()
        self.group_id = "-" + re.findall(r'\d+', self.longpoll.server)[0]
        FunPay(self).start()
        print("Bot started!")
        super().__init__(name="Main")
        self.poll()

    def parse_attachments(self):
        for attachmentList in self.attachments_last_message:
            attachment_type = attachmentList['type']
            attachment = attachmentList[attachment_type]
            access_key = attachment.get("access_key")
            if attachment_type != "sticker":
                self.attachments.append(
                    f"{attachment_type}{attachment['owner_id']}_{attachment['id']}") if access_key is None \
                    else self.attachments.append(
                    f"{attachment_type}{attachment['owner_id']}_{attachment['id']}_{access_key}")
            else:
                self.sticker_id = attachment["sticker_id"]

    def reply(self, *args, **kwargs):
        return self.user.write(*args, **kwargs)

    def wait(self, x, y):
        return cmd.set_after(x, self.user.id, y)

    def write(self, user_id, *args, **kwargs):
        user.User(self.vk, user_id).write(*args, **kwargs)

    def set_after(self, x, y=None):
        if y is None:
            y = []
        cmd.set_after(x, self.user.id, y)

    def poll(self):
        for event in self.longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                self.attachments = ListExtension()
                self.sticker_id = None
                self.user = user.User(self.vk, event.user_id)
                self.raw_text = StringExtension(event.message.strip())
                self.event = event
                self.text = StringExtension(self.raw_text.lower().strip())
                self.txtSplit = self.text.split()
                self.command = self.txtSplit[0] if len(
                    self.txtSplit) > 0 else ""
                self.args = self.txtSplit[1:]
                self.messages = self.user.messages.getHistory(count=3)["items"]
                self.last_message = self.messages[0]
                self.attachments_last_message = self.last_message["attachments"]
                self.parse_attachments()
                cmd.execute_command(self)


if __name__ == "__main__":
    _thread = MainThread()
    _thread.start()
    _thread.join()
