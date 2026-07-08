<script setup lang="ts">
import { Badge, Button, Dialog, call } from 'frappe-ui'
import { CheckCircle2, LayoutTemplate } from 'lucide-vue-next'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { createToast } from '../helpers/toasts'
import { __ } from '../translation'

export type WorkbookTemplate = {
	name: string
	title: string
	description: string
	module: string
	has_data: boolean
	preview_image: string | null
	imported_workbook: number | null
}

defineProps<{ templates: WorkbookTemplate[] }>()
const show = defineModel<boolean>({ default: false })

const router = useRouter()

// name of the template currently being imported, so only its card spins
const creating = ref<string | null>(null)

function useTemplate(template: WorkbookTemplate) {
	creating.value = template.name
	call('insights.api.templates.create_workbook_from_template', {
		template_name: template.name,
	})
		.then((name: number) => {
			createToast({ message: __('Workbook created'), variant: 'success' })
			router.push(`/workbook/${name}`)
		})
		.catch(() => {
			createToast({
				message: __('Failed to create workbook from template'),
				variant: 'error',
			})
		})
		.finally(() => (creating.value = null))
}

function openImported(template: WorkbookTemplate) {
	router.push(`/workbook/${template.imported_workbook}`)
}
</script>

<template>
	<Dialog v-model="show" :options="{ title: __('Prebuilt Workbooks'), size: '4xl' }">
		<template #body-content>
			<p class="mb-5 text-p-base text-ink-gray-6">
				{{
					__(
						'Ready-made dashboards for your installed apps. Importing one creates your own editable copy — you only need to do it once.',
					)
				}}
			</p>
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
				<div
					v-for="template in templates"
					:key="template.name"
					class="col-span-1 flex flex-col overflow-hidden rounded border border-outline-gray-1 bg-surface-white"
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
					<div class="flex flex-1 flex-col p-4">
						<div class="flex items-center justify-between gap-2">
							<div class="truncate text-base font-medium text-ink-gray-9">
								{{ template.title }}
							</div>
							<Badge v-if="template.module" theme="gray">
								{{ template.module }}
							</Badge>
						</div>
						<div class="mt-1.5 line-clamp-2 text-p-sm text-ink-gray-6">
							{{ template.description }}
						</div>

						<div
							v-if="!template.has_data && !template.imported_workbook"
							class="mt-2 text-p-sm text-ink-amber-3"
						>
							{{ __('No data found on this site — dashboards may look empty.') }}
						</div>

						<div class="mt-4 flex items-center gap-2">
							<template v-if="template.imported_workbook">
								<div class="flex items-center gap-1 text-p-sm text-ink-green-3">
									<CheckCircle2 class="h-4 w-4" />
									{{ __('Imported') }}
								</div>
								<Button class="ml-auto" @click="openImported(template)">
									{{ __('Open') }}
								</Button>
							</template>
							<Button
								v-else
								class="ml-auto"
								variant="solid"
								:loading="creating === template.name"
								:disabled="!!creating"
								@click="useTemplate(template)"
							>
								{{ __('Use template') }}
							</Button>
						</div>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>
