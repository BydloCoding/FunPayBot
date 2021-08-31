# v1.2
- Add one_time parameter to ThreadedStruct constructor: don't cache created database in thread manager 
- Add one_time parameter to ThreadedDatabase constructor: -//-
- Don't pass arguments to function, created by @command decarator if function doesn't accept any
- User class now caches avatar and user name on create
- User class can be None if provided user_id is invalid
- ListExtension.all: returns True, if function(item) returns True for all items in list

# v1.1
- Remove: db.tasks
- Feat: tasks to all threads

# v1.0
- Start on adding versions
- changed all Structs constructors (MyStruct(self.db, param1=param) -> MyStruct(param1=param))
- Feat: ThreadedDatabase.select_one_struct
- Feat: ThreadedDatabase.select_all_structs
- Feat: ThreadedStruct