from config.settings        import PROCESSED_COLLECTION_SPIDER, PROCESSED_SITES_SEO, PROCESSED_SITES_SEO_LINKS, UNPROCESSABLE_SITES
from storage.mongo_context  import MongoDbContext
from storage.repository     import Repository
from datetime               import datetime, timedelta
from queue                  import Queue
from tasks.processor        import process_batch, get_dynamic_thread_count
# (Gerekli diğer importlar: time vb. zaten dosyanın başında olabilir)

def main():
    # Ayarları yükle ve bağlan
    mongo = MongoDbContext()

    # Repository’leri oluştur
    spider_repo = Repository(PROCESSED_COLLECTION_SPIDER, mongo)
    seo_repo    = Repository(PROCESSED_SITES_SEO, mongo)
    links_repo  = Repository(PROCESSED_SITES_SEO_LINKS, mongo)
    unproc_repo = Repository(UNPROCESSABLE_SITES, mongo)

    # Kuyruk ve zaman dilimleri
    task_queue      = Queue()
    one_week_ago    = datetime.now() - timedelta(weeks=1)
    twelve_hours_ago= datetime.now() - timedelta(hours=12)

    # Yeni ve işlenmemiş kayıtları al
    new_records = spider_repo.get(
        {"$or": [
            {"last_processed_time": {"$exists": False}},
            {"last_processed_time": {"$lt": one_week_ago}}
        ]},
        limit=50
    )
    unproc = unproc_repo.get(
        {"processed_time": {"$lt": twelve_hours_ago.strftime("%Y-%m-%d %H:%M:%S")}},
        limit=50
    )

    # Kuyruğa ekle
    for rec in new_records + unproc:
        task_queue.put((rec["_id"], rec["url"]))

    # Paralel batch işlemi
    thread_count   = get_dynamic_thread_count()
    batch_results  = []
    while not task_queue.empty():
        batch = [task_queue.get() for _ in range(min(50, task_queue.qsize()))]
        batch_results.extend(process_batch(batch, thread_count))

    # Sonuçları kaydet
    # Başarılı kayıtlar
    for res in batch_results:
        seo_repo.save(res)
        links_repo.save({
            "url": res["url"],
            "processed_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        spider_repo.update(
            {"_id": res["_id"]},
            {"$set": {"last_processed_time": datetime.now()}}
        )

    # İşlenemeyen kayıtlar
    for err in unproc:
        unproc_repo.save(err)
