from django.contrib import admin
from sa_api.models import Room, Bed, Client, FileRecorded, Channel, Device, ClientBusSlot
import datetime

class ClientBusSlotInline(admin.TabularInline):
    model = ClientBusSlot
    extra = 0
    readonly_fields = ('client', 'bus', 'name', 'active', 'device')
    can_delete = False

    def get_queryset(self, request):
        return super(ClientBusSlotInline, self).get_queryset(request).filter(active=True)

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class ChannelAdmin(admin.ModelAdmin):
    list_display = ('id', 'device', 'name')

class ClientAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'mac', 'bed', 'status', 'last_connected')
    readonly_fields = ('dt_report', 'dt_start_recording', 'uptime', 'ip_address')

    inlines = [ClientBusSlotInline]

    def status(self, obj):
        if obj.registered==1:
            current_time = datetime.datetime.now()
            temp = obj.dt_update
            temp = temp.replace(tzinfo=None)
            delta = current_time - temp
            diff_seconds = int(delta.total_seconds())
            if diff_seconds < 15:
                return True
        return False

    def last_connected(self, obj):
        if obj.registered==1:
            temp = obj.dt_update
            temp = temp.replace(tzinfo=None)
            dt_string = temp.strftime("%Y-%m-%d %H:%M:%S")
            return dt_string
        return 'Not registered'

class BedAdmin(admin.ModelAdmin):
    list_display = ('id', 'room', 'name', 'bed_type')

    def bed_type(self,obj):
        bed_type_name = obj.BED_TYPE_CHOICES[obj.bed_type]
        return bed_type_name

class FileRecordedAdmin(admin.ModelAdmin):
    list_display = ('id', 'bed_name', 'room_name', 'upload_date', 'begin_date', 'end_date', 'client_mac', 'file_path')

    def client_mac(self,obj):
        return obj.client.mac

    def bed_name(self,obj):
        return obj.client.bed.name

    def room_name(self,obj):
        return obj.client.bed.room.name


# Register your models here.
admin.site.register(Device)
admin.site.register(Channel, ChannelAdmin)
admin.site.register(Room)
admin.site.register(Bed, BedAdmin)
admin.site.register(Client, ClientAdmin)
admin.site.register(FileRecorded, FileRecordedAdmin)
