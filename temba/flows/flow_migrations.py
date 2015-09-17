import copy
from uuid import uuid4
from temba.flows.models import ContainsTest, StartsWithTest, ContainsAnyTest, RegexTest, ReplyAction
from temba.flows.models import SayAction, SendAction, RuleSet


def migrate_to_version_6(json_flow):
    """
    This migration removes the non-localized flow format. This means all potentially localizable
    text will be a dict from the outset. If no language is set, we will use 'base' as thew
    default language.
    """

    # the name of the base language if its not set yet
    base_language = 'base'

    def convert_to_dict(d, key):
        if not isinstance(d[key], dict):
            d[key] = {base_language: d[key]}

    if 'base_language' not in json_flow:
        json_flow['base_language'] = base_language

        for ruleset in json_flow.get('rule_sets'):
            for rule in ruleset.get('rules'):

                # betweens haven't always required a category name, create one
                rule_test = rule['test']
                if rule_test['type'] == 'between' and 'category' not in rule:
                    rule['category'] = '%s-%s' % (rule_test['min'], rule_test['max'])

                # convert the category name
                convert_to_dict(rule, 'category')

                # convert our localized types
                if (rule['test']['type'] in [ContainsTest.TYPE, ContainsAnyTest.TYPE,
                                             StartsWithTest.TYPE, RegexTest.TYPE]):
                    convert_to_dict(rule['test'], 'test')

        for actionset in json_flow.get('action_sets'):
            for action in actionset.get('actions'):
                if action['type'] in [SendAction.TYPE, ReplyAction.TYPE, SayAction.TYPE]:
                    convert_to_dict(action, 'msg')
                if action['type'] == SayAction.TYPE:
                    convert_to_dict(action, 'recording')


def migrate_to_version_5(json_flow):
    """
    Adds passive rulesets. This necessitates injecting nodes to account for places where
    we previously waiting implicitly with explicit waits.
    """

    def requires_step(operand):

        # if we start with =( then we are an expression
        is_expression = operand and len(operand) > 2 and operand[0:2] == '=('
        if '@step' in operand or (is_expression and 'step' in operand):
            return True
        return False

    for ruleset in json_flow.get('rule_sets'):

        response_type = ruleset.pop('response_type', None)
        ruleset_type = ruleset.get('ruleset_type', None)
        label = ruleset.get('label')

        # remove config from any rules, these are turds
        for rule in ruleset.get('rules'):
            if 'config' in rule:
                del rule['config']

        if response_type and not ruleset_type:

            # webhooks now live in their own ruleset, insert one
            webhook_url = ruleset.pop('webhook', None)
            webhook_action = ruleset.pop('webhook_action', None)

            has_old_webhook = webhook_url and ruleset_type != RuleSet.TYPE_WEBHOOK

            # determine our type from our operand
            operand = ruleset.get('operand')
            if not operand:
                operand = '@step.value'

            operand = operand.strip()

            # all previous ruleset that require step should be wait_message
            if requires_step(operand):
                # if we have an empty operand, go ahead and update it
                if not operand:
                    ruleset['operand'] = '@step.value'

                if response_type == 'K':
                    ruleset['ruleset_type'] = RuleSet.TYPE_WAIT_DIGITS
                elif response_type == 'M':
                    ruleset['ruleset_type'] = RuleSet.TYPE_WAIT_DIGIT
                elif response_type == 'R':
                    ruleset['ruleset_type'] = RuleSet.TYPE_WAIT_RECORDING
                else:

                    if operand == '@step.value':
                        ruleset['ruleset_type'] = RuleSet.TYPE_WAIT_MESSAGE
                    else:

                        ruleset['ruleset_type'] = RuleSet.TYPE_EXPRESSION

                        # if it's not a plain split, make us wait and create
                        # an expression split node to handle our response
                        pausing_ruleset = copy.deepcopy(ruleset)
                        pausing_ruleset['ruleset_type'] = RuleSet.TYPE_WAIT_MESSAGE
                        pausing_ruleset['operand'] = '@step.value'
                        pausing_ruleset['label'] = label + ' Response'
                        remove_extra_rules(json_flow, pausing_ruleset)
                        insert_node(json_flow, pausing_ruleset, ruleset)

            else:
                # if there's no reference to step, figure out our type
                ruleset['ruleset_type'] = RuleSet.TYPE_EXPRESSION
                # special case contact and flow fields
                if ' ' not in operand and '|' not in operand:
                    if operand == '@contact.groups':
                        ruleset['ruleset_type'] = RuleSet.TYPE_EXPRESSION
                    elif operand.find('@contact.') == 0:
                        ruleset['ruleset_type'] = RuleSet.TYPE_CONTACT_FIELD
                    elif operand.find('@flow.') == 0:
                        ruleset['ruleset_type'] = RuleSet.TYPE_FLOW_FIELD

                # we used to stop at webhooks, now we need a new node
                # to make sure processing stops at this step now
                if has_old_webhook:
                    pausing_ruleset = copy.deepcopy(ruleset)
                    pausing_ruleset['ruleset_type'] = RuleSet.TYPE_WAIT_MESSAGE
                    pausing_ruleset['operand'] = '@step.value'
                    pausing_ruleset['label'] = label + ' Response'
                    remove_extra_rules(json_flow, pausing_ruleset)
                    insert_node(json_flow, pausing_ruleset, ruleset)

            # finally insert our webhook node if necessary
            if has_old_webhook:
                webhook_ruleset = copy.deepcopy(ruleset)
                webhook_ruleset['webhook'] = webhook_url
                webhook_ruleset['webhook_action'] = webhook_action
                webhook_ruleset['operand'] = '@step.value'
                webhook_ruleset['ruleset_type'] = RuleSet.TYPE_WEBHOOK
                webhook_ruleset['label'] = label + ' Webhook'
                remove_extra_rules(json_flow, webhook_ruleset)
                insert_node(json_flow, webhook_ruleset, ruleset)


# Helper methods for flow migrations

def remove_extra_rules(json_flow, ruleset):
    """ Remove all rules but the all responses rule """
    rules = []
    old_rules = ruleset.get('rules')
    for rule in old_rules:
        if rule['test']['type'] == 'true':
            if 'base_language' in json_flow:
                rule['category'][json_flow['base_language']] = 'All Responses'
            else:
                rule['category'] = 'All Responses'
            rules.append(rule)

    ruleset['rules'] = rules


def insert_node(flow, node, _next):
    """ Inserts a node right before _next """

    def update_destination(node_to_update, uuid):
        if node_to_update.get('actions', []):
            node_to_update['destination'] = uuid
        else:
            for rule in node_to_update.get('rules',[]):
                rule['destination'] = uuid

    # make sure we have a fresh uuid
    node['uuid'] = _next['uuid']
    _next['uuid'] = unicode(uuid4())
    update_destination(node, _next['uuid'])

    # bump everybody down
    for actionset in flow.get('action_sets'):
        if actionset.get('y') >= node.get('y'):
            actionset['y'] += 100

    for ruleset in flow.get('rule_sets'):
        if ruleset.get('y') >= node.get('y'):
            ruleset['y'] += 100

    # we are an actionset
    if node.get('actions', []):
        node.destination = _next.uuid
        flow['action_sets'].append(node)

    # otherwise point all rules to the same place
    else:
        for rule in node.get('rules', []):
            rule['destination'] = _next['uuid']
        flow['rule_sets'].append(node)