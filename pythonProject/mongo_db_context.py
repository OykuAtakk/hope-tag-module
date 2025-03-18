from pymongo import MongoClient

class MongoDbContext:
    def __init__(self, url, db_name):
        self.url = url
        self.db_name = db_name

    def get_datas_from_mongodb(self,collection_name, query={},limit=0):
        """
        Belirtilen sorgu ve limit parametrelerine göre kaynak koleksiyondan veri çeker.
        Örneğin, sadece 'last_processed_time' alanı olmayan ya da bir haftadan eski kayıtları seçmek için:
            query = {
                "$or": [
                    {"last_processed_time": {"$exists": False}},
                    {"last_processed_time": {"$lt": one_week_ago}}
                ]
            }
        """
        client = MongoClient(self.url)
        database = client[self.db_name]
        collection = database[collection_name]
        cursor = collection.find(query)
        if limit > 0:
            cursor = cursor.limit(limit)
        records = list(cursor)
        client.close()
        return records

    def save_datas_to_mongo(self, collection_name, datas):
        """
        Belirtilen koleksiyona tek bir kayıt veya kayıt listesini kaydeder.
        Eğer 'datas' sözlük ise tek kayıt (insert_one), liste ise birden fazla kayıt (insert_many) olarak ekler.
        """
        client = MongoClient(self.url)
        database = client[self.db_name]
        collection = database[collection_name]
        if isinstance(datas, list):
            collection.insert_many(datas)
        elif isinstance(datas, dict):
            collection.insert_one(datas)
        else:
            raise ValueError("Unsupported data type for saving to mongo")
        print("datas saved to:", collection_name)
        client.close()

    def update_mongo_record(self, collection_name, query, update_data):
        """
        Belirtilen koleksiyonda, verilen sorgu kriterlerine uyan ilk kaydı update eder.
        Örneğin, işleme tamamlandığında kaydın 'last_processed_time' alanını güncellemek için kullanılabilir.
        """
        client = MongoClient(self.url)
        database = client[self.db_name]
        collection = database[collection_name]
        result = collection.update_one(query, update_data)
        client.close()
        return result
