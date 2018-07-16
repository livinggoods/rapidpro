# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-07-16 17:06
from __future__ import unicode_literals

from django.db import migrations

SQL = """
CREATE INDEX IF NOT EXISTS msgs_broadcast_sending_idx ON msgs_broadcast(org_id, created_on) WHERE status = 'Q';

CREATE INDEX msgs_broadcasts_org_created_id_where_active
ON msgs_broadcast(org_id, created_on DESC, id DESC)
WHERE is_active = true;

CREATE INDEX msgs_msg_channel_external_id_not_null
ON msgs_msg (channel_id, external_id)
WHERE external_id IS NOT NULL;

CREATE INDEX msgs_msg_contact_id_created_on ON msgs_msg (contact_id, created_on desc);

CREATE INDEX msgs_msg_org_created_id_where_outbound_visible_failed
ON msgs_msg(org_id, created_on DESC, id DESC)
WHERE direction = 'O' AND visibility = 'V' AND status = 'F';

CREATE INDEX msgs_msg_org_created_id_where_outbound_visible_outbox
ON msgs_msg(org_id, created_on DESC, id DESC)
WHERE direction = 'O' AND visibility = 'V' AND status IN ('P', 'Q');

CREATE INDEX msgs_msg_org_created_id_where_outbound_visible_sent
ON msgs_msg(org_id, created_on DESC, id DESC)
WHERE direction = 'O' AND visibility = 'V' AND status IN ('W', 'S', 'D');

CREATE INDEX IF NOT EXISTS msgs_msg_org_id_created_on_id_idx on msgs_msg(org_id, created_on, id);

CREATE INDEX msgs_msg_org_modified_id_where_inbound
ON msgs_msg (org_id, modified_on DESC, id DESC)
WHERE direction = 'I';

CREATE INDEX msgs_msg_responded_to_not_null
ON msgs_msg (response_to_id)
WHERE response_to_id IS NOT NULL;

CREATE INDEX msgs_msg_uuid_not_null ON msgs_msg (uuid) WHERE uuid IS NOT NULL;

CREATE INDEX msgs_msg_visibility_type_created_id_where_inbound
ON msgs_msg(org_id, visibility, msg_type, created_on DESC, id DESC)
WHERE direction = 'I';

-- index for fast fetching of unsquashed rows
CREATE INDEX msgs_systemlabel_unsquashed
ON msgs_systemlabelcount(org_id, label_type) WHERE NOT is_squashed;
"""


class Migration(migrations.Migration):

    dependencies = [("msgs", "0001_initial")]

    operations = [migrations.RunSQL(SQL)]
