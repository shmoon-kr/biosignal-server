from django.contrib.admin.widgets import AdminFileWidget
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.contrib import admin
from sa_api.models import Room, Bed, Client, FileRecorded, Channel, Device, ClientBusSlot, Review
import datetime


class AdminImageWidget(AdminFileWidget):
    def render(self, name, value, attrs=None):
        output = []
        if value and getattr(value, "url", None):
            image_url = value.url
            file_name = str(value)
            output.append(u' <a href="%s" target="_blank"><img src="%s" alt="%s" /></a> %s ' % \
                          (image_url, image_url, file_name, _('Change:')))
        output.append(super(AdminFileWidget, self).render(name, value, attrs))
        return mark_safe(u''.join(output))


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
    list_display = ('id', 'name', 'mac', 'bed', 'slot', 'status', 'dt_report')
    readonly_fields = ('dt_report', 'dt_start_recording', 'uptime', 'ip_address')

    inlines = [ClientBusSlotInline]

    def slot(self, obj):
        active_slot = ClientBusSlot.objects.filter(client=obj, active=True)
        found_device = active_slot.exclude(device__isnull=True)
        return '%d/%d' % (found_device.count(), active_slot.count())

    '''
    def get_ordering(self, request):
        return ['bed']
    '''


class BedAdmin(admin.ModelAdmin):
    list_display = ('id', 'room', 'name', 'bed_type')

    def bed_type(self, obj):
        bed_type_name = obj.BED_TYPE_CHOICES[obj.bed_type]
        return bed_type_name


class FileRecordedAdmin(admin.ModelAdmin):
    list_display = ('id', 'bed_name', 'room_name', 'upload_date', 'begin_date', 'end_date', 'client_mac', 'file_path')

    def client_mac(self, obj):
        return obj.client.mac

    def bed_name(self, obj):
        return obj.client.bed.name

    def room_name(self, obj):
        return obj.client.bed.room.name


class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'org', 'name', 'bed_name', 'room_name', 'dt_report', 'exist_comment')
    readonly_fields = ('name', 'bed', 'dt_report', 'chart_image', 'local_server_name')

    def org(self, obj):
        return obj.local_server_name

    def bed_name(self, obj):
        return obj.bed.name

    def room_name(self, obj):
        return obj.bed.room.name

    def exist_comment(self, obj):
        return obj.comment != ''

    def chart_image(self, obj):
        return mark_safe('<img src="{url}" width="{width}" height={height} />'.format(
            url=obj.chart.url,
            width=obj.chart.width,
            height=obj.chart.height,
            )
        )

# Register your models here.
admin.site.register(Device)
admin.site.register(Channel, ChannelAdmin)
admin.site.register(Room)
admin.site.register(Bed, BedAdmin)
admin.site.register(Client, ClientAdmin)
admin.site.register(FileRecorded, FileRecordedAdmin)
admin.site.register(Review, ReviewAdmin)
