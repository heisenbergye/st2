# Licensed to the StackStorm, Inc ('StackStorm') under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import six

# http://docs.mongodb.org/manual/faq/developers/#faq-dollar-sign-escaping
UNESCAPED = ['.', '$']
ESCAPED = [u'\uFF0E', u'\uFF04']
ESCAPE_TRANSLATION = dict(zip(UNESCAPED, ESCAPED))
UNESCAPE_TRANSLATION = dict(zip(ESCAPED, UNESCAPED))


def _translate_chars(field, translation):
    # Only translate the fields of a dict
    if not isinstance(field, dict):
        return field
    work_items = [(k, v, field) for k, v in six.iteritems(field)]
    while len(work_items) > 0:
        work_item = work_items.pop(0)
        oldkey = work_item[0]
        value = work_item[1]
        work_field = work_item[2]
        newkey = oldkey
        for t_k, t_v in six.iteritems(translation):
            newkey = newkey.replace(t_k, t_v)
        if newkey != oldkey:
            work_field[newkey] = value
            del work_field[oldkey]
        if isinstance(value, dict):
            nested_work_items = [(k, v, value) for k, v in six.iteritems(value)]
            work_items.extend(nested_work_items)
    return field


def escape_chars(field):
    return _translate_chars(field, ESCAPE_TRANSLATION)


def unescape_chars(field):
    return _translate_chars(field, UNESCAPE_TRANSLATION)
