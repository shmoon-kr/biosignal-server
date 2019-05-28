import datetime
from django.contrib.admin.widgets import AdminFileWidget
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.contrib import admin
from sa_api.models import Room, Bed, Client, FileRecorded, Channel, Device, ClientBusSlot, Review, AnesthesiaRecordEvent, AnesthesiaRecord


def parse_anesthesia_record(text):
    event_cat = list()
    event_cat.append('')
    event_cat.append('')
    event_cat.append('')

    events = list()

    eventnum = 0

    for l in text.splitlines():
        line = l.rstrip().lstrip()
        if '■ 마취제(Anesthetics) 포함 약물 정보' in line:
            event_cat[0] = 'GasDrug'
        elif '■ Input' in line:
            event_cat[0] = 'I'
            event_cat[1] = 'I'
        elif '■ Output' in line:
            event_cat[0] = 'O'
        elif '■ 마취 기록 이벤트 내용' in line:
            event_cat[0] = 'E'
            event_cat[1] = 'E'
            event_cat[2] = 'E'
        elif line == 'U/O':
            event_cat[1] = 'U/O'
            event_cat[2] = 'U/O'
        elif line == 'Gas':
            event_cat[1] = 'Gas'
        elif line == 'Drug':
            event_cat[1] = 'Drug'
        elif line == 'O2':
            event_cat[2] = 'O2'
        elif line.startswith('ⓑ ') or line.startswith('ⓒ '):
            event_cat[2] = line[2:]
        elif line.startswith('- '):
            try:
                dt = datetime.datetime.strptime(line.split(' ')[1][:-1], '%H:%M')
                desc = line[line.find(', ') + 2:]
                events.append(event_cat + [dt.time(), desc])
            except Exception as e:
                pass
        elif line != '':
            try:
                ls = line.split(' ')
                assert int(float(ls[0])) == (eventnum + 1), 'Wrong Event Number'
                dt = datetime.datetime.strptime(line.split(' ')[1], '%H:%M')
                eventnum += 1
                desc = line[line.find(' - ') + 3:]
                events.append(event_cat + [dt.time(), desc])
            except Exception as e:
                if event_cat[0] == 'E':
                    events[-1][-1] += ' ' + line
                pass

    return events


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


class AnesthesiaRecordEventInline(admin.TabularInline):
    model = AnesthesiaRecordEvent
    extra = 0
    readonly_fields = ('dt', 'category', 'description')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class AnesthesiaRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'bed', 'dt_operation')

    inlines = [AnesthesiaRecordEventInline]

    def save_model(self, request, obj, form, change):
        events = parse_anesthesia_record(obj.raw_record)
        AnesthesiaRecordEvent.objects.filter(record=obj).delete()
        for event in events:
            dt = datetime.datetime.combine(obj.dt_operation, event[3])
            AnesthesiaRecordEvent.objects.create(dt=dt, record=obj, category=event[2], description=event[4])
        super(AnesthesiaRecordAdmin, self).save_model(request, obj, form, change)


class ChannelAdmin(admin.ModelAdmin):
    list_display = ('id', 'device', 'unk', 'name', 'colored_abbreviation', 'rec_fmt', 'unit', 'min', 'max', 'srate')
    list_filter = ('device', 'is_unknown')

    def unk(self, obj):
        return obj.is_unknown

    def min(self, obj):
        return obj.minval

    def max(self, obj):
        return obj.maxval

    def rec_fmt(self, obj):
        return obj.RECORDING_FORMAT_CHOICES[obj.recording_format]


class ClientAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'mac', 'ver', 'colored_bed', 'slot', 'status', 'dt_report')
    readonly_fields = ('dt_report', 'dt_start_recording', 'uptime', 'ip_address')

    inlines = [ClientBusSlotInline]

    def ver(self, obj):
        return obj.client_version

    def slot(self, obj):
        active_slot = ClientBusSlot.objects.filter(client=obj, active=True)
        found_device = active_slot.exclude(device__isnull=True)
        return '%d/%d' % (found_device.count(), active_slot.count())

    def get_ordering(self, request):
        return ['bed__name']


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
admin.site.register(AnesthesiaRecord, AnesthesiaRecordAdmin)
