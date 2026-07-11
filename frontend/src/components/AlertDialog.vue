<script setup>
import Code from '@/components/Controls/Code.vue'
import useQuery from '@/query/resources/useQuery'
import { createResource } from 'frappe-ui'
import { TextEditor } from 'frappe-ui'
import { computed, reactive, inject } from 'vue'

const emit = defineEmits(['update:show'])
const props = defineProps({
	show: Boolean,
	queryName: String,
})

const show = computed({
	get: () => props.show,
	set: (value) => {
		emit('update:show', value)
	},
})

let query = inject('query')
if (!query) query = useQuery(props.queryName)
const alert = reactive({
	title: '',
	query: props.queryName,
	frequency: 'Daily',
	cron: null,
	channel: 'Email',
	recipients: '',
	telegram_chat_id: null,
	condition: {
		isAdvanced: false,
		left: '',
		operator: '=',
		right: null,
		advanceCondition: null,
	},
	message: null,
})

const frequencyOptions = [
	{ value: 'Hourly', label: __('Check once an hour') },
	{ value: 'Daily', label: __('Check once a day') },
	{ value: 'Weekly', label: __('Check once a week') },
	{ value: 'Monthly', label: __('Check once a month') },
	{ value: 'Custom', label: __('Custom') },
]
const channelOptions = [
	{ label: __('Email'), value: 'Email' },
	{ label: __('Telegram'), value: 'Telegram' },
]
const operatorOptions = ['=', '!=', '>', '>=', '<', '<=']
const createAlertDisabled = computed(() => {
	if (!alert.title) return true
	if (!alert.frequency) return true
	if (alert.frequency === 'Custom' && !alert.cron) return true
	if (!alert.channel) return true
	if (alert.channel === 'Email' && !alert.recipients) return true
	if (alert.channel === 'Telegram' && !alert.telegram_chat_id) return true
	if (alert.condition.isAdvanced && !alert.condition.advanceCondition) return true
	if (!alert.condition.isAdvanced && !alert.condition.left) return true
	if (!alert.condition.isAdvanced && !alert.condition.operator) return true
	if (!alert.condition.isAdvanced && !alert.condition.right) return true
	return false
})
const createAlertResource = createResource({ url: 'insights.api.alerts.create_alert' })
function makeCondition() {
	return alert.condition.isAdvanced
		? alert.condition.advanceCondition
		: `any(results['${alert.condition.left}'] ${alert.condition.operator} ${alert.condition.right})`
}
function createAlert() {
	if (createAlertDisabled.value) return
	const _alert = { ...alert }
	_alert.condition = makeCondition()
	createAlertResource
		.submit({
			alert: _alert,
		})
		.then((res) => {
			console.log(res)
			show.value = false
		})
}
const testAlertResource = createResource({ url: 'insights.api.alerts.test_alert' })
function testSendAlert() {
	if (createAlertDisabled.value) return
	const _alert = { ...alert }
	_alert.condition = makeCondition()
	testAlertResource
		.submit({
			alert: _alert,
		})
		.then((res) => {
			console.log(res)
		})
}
</script>

<template>
	<Dialog :options="{ title: __('Create Alert') }" v-model="show" :dismissable="true">
		<template #body-content>
			<div class="space-y-4 text-base">
				<div class="flex gap-4">
					<div class="flex flex-1 flex-col space-y-4">
						<Input
							type="text"
							:label="__('Alert Name')"
							v-model="alert.title"
							:placeholder="__('e.g. Low Inventory')"
						/>
						<Input
							type="select"
							:label="__('Frequency')"
							v-model="alert.frequency"
							:options="frequencyOptions"
						/>
						<Input
							v-if="alert.frequency === 'Custom'"
							type="text"
							:label="__('Cron')"
							v-model="alert.cron"
							placeholder="e.g. 0 0 12 * * ?"
						/>
					</div>
					<div class="flex flex-1 flex-col space-y-4">
						<Input
							type="select"
							:label="__('Channel')"
							v-model="alert.channel"
							:options="channelOptions"
						/>
						<Input
							v-if="alert.channel === 'Email'"
							type="text"
							:label="__('Recipients')"
							v-model="alert.recipients"
							:placeholder="__('e.g. john@example.com, henry@example.com')"
						/>
						<Input
							v-if="alert.channel === 'Telegram'"
							type="text"
							:label="__('Telegram Chat ID')"
							v-model="alert.telegram_chat_id"
							placeholder="e.g. 123456789"
						/>
					</div>
				</div>

				<div class="space-y-4">
					<p class="text-lg font-medium text-gray-800">{{ __('Send alert when') }}</p>
					<div class="!mt-2 flex gap-4" v-if="!alert.condition.isAdvanced">
						<Input
							type="select"
							class="flex-1"
							v-model="alert.condition.left"
							:options="
								query.results.columns.map((c) => ({
									label: c.label,
									value: c.label,
									description: c.type,
								}))
							"
						/>
						<Input
							type="select"
							class="flex-1"
							v-model="alert.condition.operator"
							:options="operatorOptions"
						/>
						<Input
							type="text"
							class="flex-1"
							v-model="alert.condition.right"
							:placeholder="__('e.g. 100')"
						/>
					</div>
					<div v-else class="!mt-2">
						<div class="form-textarea h-20">
							<Code
								v-model="alert.condition.advanceCondition"
								:placeholder="__('Write a python expression...')"
							/>
						</div>
						<p class="font-code mt-1 text-sm text-gray-600">
							{{ __('Example: results["Count of Records"][0] > 100') }}
						</p>
					</div>
					<Input
						type="checkbox"
						:label="__('Use Advanced Condition')"
						v-model="alert.condition.isAdvanced"
					/>
				</div>

				<div>
					<p class="text-lg font-medium text-gray-800">
						{{ __('Message') }} <span class="text-sm font-normal">({{ __('Optional') }})</span>
					</p>
					<Input
						type="textarea"
						class="mt-1 h-40"
						v-model="alert.message"
						:placeholder="`e.g. 
Hey,
We have **low inventory** for **{{ title }}**.
Please order more.
Thanks,
						`"
					/>
					<p class="mt-2 text-sm text-gray-600">
						{{ __('You can use all the fields from the query like') }}
						<span class="font-code px-1"> title, data_source </span>
						{{ __('etc. like this') }}
						<span class="font-code px-1" v-html="'{{ title }}'"></span>
					</p>
				</div>
			</div>
		</template>
		<template #actions>
			<Button
				variant="solid"
				:disabled="createAlertDisabled"
				:loading="createAlertResource.loading"
				class="mr-2"
				@click="createAlert"
			>
				{{ __('Create') }}
			</Button>
			<Button
				:disabled="createAlertDisabled"
				:loading="testSendAlert.loading"
				@click="testSendAlert"
			>
				{{ __('Test') }}
			</Button>
		</template>
	</Dialog>
</template>
