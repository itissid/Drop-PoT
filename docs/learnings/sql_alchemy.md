I have never formally come across ORMs. I was wondering what this declarative_base() 
business is all about. From ChatGPT the idea is to create 
a middle layer to make querying and retrieval easier and efficient:


Logical Role of declarative_base:

    Metadata Storage: It holds the MetaData object, which is a registry that includes the ability to emit a limited set of schema generation commands to the database.

    Table Mapping: It allows you to create a new class that automatically maps to a database table. The class will have attributes mapped to table columns.

    ORM Features: It provides all the features of SQLAlchemy's ORM layer. This means you can query and manipulate data in the database directly through your Python classes, without having to write raw SQL queries.

    Inheritance: By inheriting from the base class, you can ensure that all your models have certain common attributes or methods, if needed.

    Schema Management: It plays a crucial role when you are using migration tools like Alembic, as the MetaData object can be used to identify changes in the schema for generating migration scripts.

For more details, you can refer to the official SQLAlchemy documentation:

    SQLAlchemy Declarative System
    SQLAlchemy MetaData

These are the authoritative resources on how declarative_base and the SQLAlchemy ORM function.