class DatabaseRouter:
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'listings' and model.__name__ == 'Data':
            return 'kadastra'
        return 'default'
    
    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'listings' and model.__name__ == 'Data':
            return 'kadastra'
        return 'default'
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'listings' and model_name == 'data':
            return db == 'kadastra'
        return db == 'default'
