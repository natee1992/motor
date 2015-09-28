.. currentmodule:: motor.motor_asyncio

Tutorial: Using Motor With `asyncio`
====================================

.. These setups are redundant because I can't figure out how to make doctest
  run a common setup *before* the setup for the two groups. A "testsetup:: *"
  is the obvious answer, but it's run *after* group-specific setup.

.. testsetup:: before-inserting-2000-docs

  import pymongo
  import motor.motor_asyncio
  import asyncio
  from asyncio import coroutine
  db = motor.motor_asyncio.AsyncIOMotorClient().test_database

.. testsetup:: after-inserting-2000-docs

  import pymongo
  import motor.motor_asyncio
  import asyncio
  from asyncio import coroutine
  db = motor.motor_asyncio.AsyncIOMotorClient().test_database
  pymongo.MongoClient().test_database.test_collection.insert(
      [{'i': i} for i in range(2000)])

.. testcleanup:: *

  import pymongo
  pymongo.MongoClient().test_database.test_collection.remove()

A guide to using MongoDB and asyncio with Motor, the
non-blocking driver.

Tutorial Prerequisites
----------------------
You can learn about MongoDB with the `MongoDB Tutorial`_ before you learn Motor.

Using Python 3.4 or later, do::

  $ python3 -m pip install motor

This tutorial assumes that a MongoDB instance is running on the
default host and port. Assuming you have `downloaded and installed
<http://docs.mongodb.org/manual/installation/>`_ MongoDB, you
can start it like so:

.. code-block:: bash

  $ mongod

.. _pip: http://www.pip-installer.org/en/latest/installing.html

.. _MongoDB Tutorial: http://docs.mongodb.org/manual/tutorial/getting-started/

Object Hierarchy
----------------
Motor, like PyMongo, represents data with a 4-level object hierarchy:

* `AsyncIOMotorClient` / `AsyncIOMotorReplicaSetClient`:
  represents a mongod process, or a cluster of them. You explicitly create one
  of these client objects, connect it to a running mongod or mongods, and
  use it for the lifetime of your application.
* `AsyncIOMotorDatabase`: Each mongod has a set of databases (distinct
  sets of data files on disk). You can get a reference to a database from a
  client.
* `AsyncIOMotorCollection`: A database has a set of collections, which
  contain documents; you get a reference to a collection from a database.
* `AsyncIOMotorCursor`: Executing `AsyncIOMotorCollection.find` on
  an `AsyncIOMotorCollection` gets an `AsyncIOMotorCursor`, which
  represents the set of documents matching a query.

Creating a Client
-----------------
You typically create a single instance of either `AsyncIOMotorClient`
or `AsyncIOMotorReplicaSetClient` at the time your application starts
up. (See `high availability and PyMongo`_ for an introduction to
MongoDB replica sets and how PyMongo connects to them.)

.. doctest:: before-inserting-2000-docs

  >>> client = motor.motor_asyncio.AsyncIOMotorClient()

This connects to a ``mongod`` listening on the default host and port. You can
specify the host and port like:

.. doctest:: before-inserting-2000-docs

  >>> client = motor.motor_asyncio.AsyncIOMotorClient('localhost', 27017)

Motor also supports `connection URIs`_:

.. doctest:: before-inserting-2000-docs

  >>> client = motor.motor_asyncio.AsyncIOMotorClient('mongodb://localhost:27017')

.. _high availability and PyMongo: http://api.mongodb.org/python/current/examples/high_availability.html

.. _connection URIs: http://docs.mongodb.org/manual/reference/connection-string/

Getting a Database
------------------
A single instance of MongoDB can support multiple independent
`databases <http://docs.mongodb.org/manual/reference/glossary/#term-database>`_.
From an open client, you can get a reference to a particular database with
dot-notation or bracket-notation:

.. doctest:: before-inserting-2000-docs

  >>> db = client.test_database
  >>> db = client['test_database']

Creating a reference to a database does no I/O and does not require a
``yield from`` statement.

Getting a Collection
--------------------
A `collection <http://docs.mongodb.org/manual/reference/glossary/#term-collection>`_
is a group of documents stored in MongoDB, and can be thought of as roughly
the equivalent of a table in a relational database. Getting a
collection in Motor works the same as getting a database:

.. doctest:: before-inserting-2000-docs

  >>> collection = db.test_collection
  >>> collection = db['test_collection']

Just like getting a reference to a database, getting a reference to a
collection does no I/O and doesn't require a ``yield from`` statement.

Inserting a Document
--------------------
As in PyMongo, Motor represents MongoDB documents with Python dictionaries. To
store a document in MongoDB, call `AsyncIOMotorCollection.insert` in a
``yield from`` statement:

.. doctest:: before-inserting-2000-docs

  >>> @coroutine
  ... def do_insert():
  ...     document = {'key': 'value'}
  ...     result = yield from db.test_collection.insert(document)
  ...     print('result %s' % repr(result))
  ...
  >>>
  >>> loop = asyncio.get_event_loop()
  >>> loop.run_until_complete(do_insert())
  result ObjectId('...')

.. mongodoc:: insert

Getting a Single Document With `find_one`
-----------------------------------------

Use `AsyncIOMotorCollection.find_one` to get the first document that
matches a query. For example, to get a document where the value for key "i" is
less than 2:

.. doctest:: after-inserting-2000-docs

  >>> @coroutine
  ... def do_find_one():
  ...     document = yield from db.test_collection.find_one({'i': {'$lt': 2}})
  ...     pprint.pprint(document)
  ...
  >>> loop = asyncio.get_event_loop()
  >>> loop.run_until_complete(do_find_one())
  {'_id': ObjectId('...'), 'i': 0}

The result is a dictionary matching the one that we inserted previously.

.. note:: The returned document contains an ``"_id"``, which was
   automatically added on insert.

.. mongodoc:: find

Querying for More Than One Document
-----------------------------------
Use `AsyncIOMotorCollection.find` to query for a set of documents.
`AsyncIOMotorCollection.find` does no I/O and does not require a ``yield from``
statement. It merely creates an `AsyncIOMotorCursor` instance. The query is
actually executed on the server when you call `AsyncIOMotorCursor.to_list` or
`AsyncIOMotorCursor.each`, or yield from :attr:`~motor.motor_asyncio.AsyncIOMotorCursor.fetch_next`.

To find all documents with "i" less than 5:

.. doctest:: after-inserting-2000-docs

  >>> @coroutine
  ... def do_find():
  ...     cursor = db.test_collection.find({'i': {'$lt': 5}})
  ...     for document in (yield from cursor.to_list(length=100)):
  ...         pprint.pprint(document)
  ...
  >>> loop = asyncio.get_event_loop()
  >>> loop.run_until_complete(do_find())
  {'_id': ObjectId('...'), 'i': 0}
  {'_id': ObjectId('...'), 'i': 1}
  {'_id': ObjectId('...'), 'i': 2}
  {'_id': ObjectId('...'), 'i': 3}
  {'_id': ObjectId('...'), 'i': 4}

A ``length`` argument is required when you call ``to_list`` to prevent Motor
from buffering an unlimited number of documents.

To get one document at a time with :attr:`~motor.motor_asyncio.AsyncIOMotorCursor.fetch_next`
and `AsyncIOMotorCursor.next_object`:

.. doctest:: after-inserting-2000-docs

  >>> @coroutine
  ... def do_find():
  ...     cursor = db.test_collection.find({'i': {'$lt': 5}})
  ...     while (yield from cursor.fetch_next):
  ...         document = cursor.next_object()
  ...         pprint.pprint(document)
  ...
  >>> loop = asyncio.get_event_loop()
  >>> loop.run_until_complete(do_find())
  {'_id': ObjectId('...'), 'i': 0}
  {'_id': ObjectId('...'), 'i': 1}
  {'_id': ObjectId('...'), 'i': 2}
  {'_id': ObjectId('...'), 'i': 3}
  {'_id': ObjectId('...'), 'i': 4}

You can apply a sort, limit, or skip to a query before you begin iterating:

.. doctest:: after-inserting-2000-docs

  >>> @coroutine
  ... def do_find():
  ...     cursor = db.test_collection.find({'i': {'$lt': 5}})
  ...     # Modify the query before iterating
  ...     cursor.sort([('i', pymongo.DESCENDING)]).limit(2).skip(2)
  ...     while (yield from cursor.fetch_next):
  ...         document = cursor.next_object()
  ...         pprint.pprint(document)
  ...
  >>> loop = asyncio.get_event_loop()
  >>> loop.run_until_complete(do_find())
  {'_id': ObjectId('...'), 'i': 2}
  {'_id': ObjectId('...'), 'i': 1}

``fetch_next`` does not actually retrieve each document from the server
individually; it gets documents efficiently in `large batches`_.

.. _`large batches`: http://docs.mongodb.org/manual/core/read-operations/#cursor-behaviors

Counting Documents
------------------
Use `AsyncIOMotorCursor.count` to determine the number of documents in
a collection, or the number of documents that match a query:

.. doctest:: after-inserting-2000-docs

  >>> @coroutine
  ... def do_count():
  ...     n = yield from db.test_collection.find().count()
  ...     print('%s documents in collection' % n)
  ...     n = yield from db.test_collection.find({'i': {'$gt': 1000}}).count()
  ...     print('%s documents where i > 1000' % n)
  ...
  >>> loop = asyncio.get_event_loop()
  >>> loop.run_until_complete(do_count())
  2000 documents in collection
  999 documents where i > 1000

`AsyncIOMotorCursor.count` uses the *count command* internally; we'll
cover commands_ below.

.. seealso:: `Count command <http://docs.mongodb.org/manual/reference/command/count/>`_

Updating Documents
------------------
`AsyncIOMotorCollection.update` changes documents. It requires two
parameters: a *query* that specifies which documents to update, and an update
document. The query follows the same syntax as for :meth:`find` or
:meth:`find_one`. The update document has two modes: it can replace the whole
document, or it can update some fields of a document. To replace a document:

.. doctest:: after-inserting-2000-docs

  >>> @coroutine
  ... def do_replace():
  ...     coll = db.test_collection
  ...     old_document = yield from coll.find_one({'i': 50})
  ...     print('found document: %s' % pprint.pformat(old_document))
  ...     _id = old_document['_id']
  ...     result = yield from coll.update({'_id': _id}, {'key': 'value'})
  ...     print('replaced %s document' % result['n'])
  ...     new_document = yield from coll.find_one({'_id': _id})
  ...     print('document is now %s' % pprint.pformat(new_document))
  ...
  >>> loop = asyncio.get_event_loop()
  >>> loop.run_until_complete(do_replace())
  found document: {'_id': ObjectId('...'), 'i': 50}
  replaced 1 document
  document is now {'_id': ObjectId('...'), 'key': 'value'}

You can see that :meth:`update` replaced everything in the old document except
its ``_id`` with the new document.

Use MongoDB's modifier operators to update part of a document and leave the
rest intact. We'll find the document whose "i" is 51 and use the ``$set``
operator to set "key" to "value":

.. doctest:: after-inserting-2000-docs

  >>> @coroutine
  ... def do_update():
  ...     coll = db.test_collection
  ...     result = yield from coll.update({'i': 51}, {'$set': {'key': 'value'}})
  ...     print('updated %s document' % result['n'])
  ...     new_document = yield from coll.find_one({'i': 51})
  ...     print('document is now %s' % pprint.pformat(new_document))
  ...
  >>> loop = asyncio.get_event_loop()
  >>> loop.run_until_complete(do_update())
  updated 1 document
  document is now {'_id': ObjectId('...'), 'i': 51, 'key': 'value'}

"key" is set to "value" and "i" is still 51.

By default :meth:`update` only affects the first document it finds, you can
update all of them with the ``multi`` flag::

    yield from coll.update({'i': {'$gt': 100}}, {'$set': {'key': 'value'}}, multi=True)

.. mongodoc:: update

Saving Documents
----------------

`AsyncIOMotorCollection.save` is a convenience method provided to insert
a new document or update an existing one. If the dict passed to :meth:`save`
has an ``"_id"`` key then Motor performs an :meth:`update` (upsert) operation
and any existing document with that ``"_id"`` is overwritten. Otherwise Motor
performs an :meth:`insert`.

.. doctest:: after-inserting-2000-docs

  >>> @coroutine
  ... def do_save():
  ...     coll = db.test_collection
  ...     doc = {'key': 'value'}
  ...     yield from coll.save(doc)
  ...     print('document _id: %s' % repr(doc['_id']))
  ...     doc['other_key'] = 'other_value'
  ...     yield from coll.save(doc)
  ...     yield from coll.remove(doc)
  ...
  >>> loop = asyncio.get_event_loop()
  >>> loop.run_until_complete(do_save())
  document _id: ObjectId('...')

Removing Documents
------------------

`AsyncIOMotorCollection.remove` takes a query with the same syntax as
`AsyncIOMotorCollection.find`.
:meth:`remove` immediately removes all matching documents.

.. doctest:: after-inserting-2000-docs

  >>> @coroutine
  ... def do_remove():
  ...     coll = db.test_collection
  ...     n = yield from coll.count()
  ...     print('%s documents before calling remove()' % n)
  ...     result = yield from db.test_collection.remove({'i': {'$gte': 1000}})
  ...     print('%s documents after' % (yield from coll.count()))
  ...
  >>> loop = asyncio.get_event_loop()
  >>> loop.run_until_complete(do_remove())
  2000 documents before calling remove()
  1000 documents after

.. mongodoc:: remove

Commands
--------
Besides the "CRUD" operations--insert, update, remove, and find--all other
operations on MongoDB are commands. Run them using
the `AsyncIOMotorDatabase.command` method on `AsyncIOMotorDatabase`:

.. doctest:: after-inserting-2000-docs

  >>> from bson import SON
  >>> @coroutine
  ... def use_count_command():
  ...     response = yield from db.command(SON([("count", "test_collection")]))
  ...     print('response: %s' % pprint.pformat(response))
  ...
  >>> loop = asyncio.get_event_loop()
  >>> loop.run_until_complete(use_count_command())
  response: {'n': 1000, 'ok': 1.0}

Since the order of command parameters matters, don't use a Python dict to pass
the command's parameters. Instead, make a habit of using :class:`bson.SON`,
from the ``bson`` module included with PyMongo::

    yield from db.command(SON([("distinct", "test_collection"), ("key", "my_key"]))

Many commands have special helper methods, such as
`AsyncIOMotorDatabase.create_collection` or
`AsyncIOMotorCollection.aggregate`, but these are just conveniences atop
the basic :meth:`command` method.

.. mongodoc:: commands

Further Reading
---------------
Learning to use the MongoDB driver is just the beginning, of course. For
in-depth instruction in MongoDB itself, see `The MongoDB Manual`_.

.. _The MongoDB Manual: http://docs.mongodb.org/manual/