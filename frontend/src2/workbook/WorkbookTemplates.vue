<script setup lang="ts">
import { Badge, call } from 'frappe-ui'
import { LayoutTemplate } from 'lucide-vue-next'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { confirmDialog } from '../helpers/confirm_dialog'
import { createToast } from '../helpers/toasts'
import { __ } from '../translation'

type WorkbookTemplate = {
	name: string
	title: string
	description: string
	module: string
	has_data: boolean
	preview_image: string | null
}

const router = useRouter()

const templates = ref<WorkbookTemplate[]>([])
call('insights.api.templates.get_workbook_templates').then(
	(data: WorkbookTemplate[]) => (templates.value = data || []),
)

const creating = ref(false)
function createFromTemplate(template: WorkbookTemplate) {
	confirmDialog({
		title: __('Start with a template'),
		message: template.has_data
			? __('This will create a new workbook from the "{0}" template.', template.title)
			: __(
					'This will create a new workbook from the "{0}" template. No data was found for it on this site, so its dashboards may look empty.',
					template.title,
			  ),
		primaryActionLabel: __('Create Workbook'),
		onSuccess: () => {
			creating.value = true
			call('insights.api.templates.create_workbook_from_template', {
				template_name: template.name,
			})
				.then((name: string) => {
					createToast({
						message: __('Workbook created successfully'),
						variant: 'success',
					})
					router.push(`/workbook/${name}`)
				})
				.catch(() => {
					createToast({
						message: __('Failed to create workbook from template'),
						variant: 'error',
					})
				})
				.finally(() => (creating.value = false))
		},
	})
}
</script>

<template>
	<div v-if="templates.length" class="flex flex-col gap-2.5">
		<div class="text-base font-medium text-ink-gray-8">{{ __('Start with a template') }}</div>
		<div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
			<div
				v-for="template in templates"
				:key="template.name"
				class="col-span-1 flex cursor-pointer flex-col overflow-hidden rounded border border-outline-gray-1 bg-surface-white transition-all hover:border-outline-gray-3"
				:class="creating ? 'pointer-events-none opacity-60' : ''"
				@click="createFromTemplate(template)"
			>
				<div class="h-32 w-full border-b border-outline-gray-1 bg-surface-gray-1">
					<img
						v-if="template.preview_image"
						:src="template.preview_image"
						:alt="template.title"
						class="h-full w-full object-cover"
					/>
					<div v-else class="flex h-full w-full items-center justify-center">
						<LayoutTemplate class="h-8 w-8 text-ink-gray-4" stroke-width="1.5" />
					</div>
				</div>
				<div class="flex flex-1 flex-col space-y-1.5 p-4">
					<div class="flex items-center justify-between gap-2">
						<div class="truncate text-base font-medium text-ink-gray-9">
							{{ template.title }}
						</div>
						<Badge v-if="template.module" theme="blue">{{ template.module }}</Badge>
					</div>
					<div class="line-clamp-2 text-sm text-ink-gray-6">
						{{ template.description }}
					</div>
				</div>
			</div>
		</div>
	</div>
</template>
