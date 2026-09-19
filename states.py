from aiogram.fsm.state import State, StatesGroup


class AddVideoStates(StatesGroup):
    waiting_for_video = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_position = State()


class EditVideoStates(StatesGroup):
    waiting_for_new_value = State()


class UpdateVideoFileStates(StatesGroup):
    waiting_for_video = State()


class SearchUserStates(StatesGroup):
    waiting_for_id = State()
    waiting_for_username = State()


class VotingPeriodStates(StatesGroup):
    waiting_for_start = State()
    waiting_for_end = State()


class AddAdminStates(StatesGroup):
    waiting_for_id = State()


class BroadcastStates(StatesGroup):
    waiting_for_message = State()
