<template>
	<Dialog :options="{ title: __('Add User') }" v-model="show">
		<template #body-content>
			<Form
				v-model="newUser"
				:meta="{
					fields: [
						{
							name: 'first_name',
							label: __('First Name'),
							type: 'text',
							placeholder: __('Enter first name'),
						},
						{
							name: 'last_name',
							label: __('Last Name'),
							type: 'text',
							placeholder: __('Enter last name'),
						},
						{
							name: 'email',
							label: __('Email'),
							type: 'email',
							placeholder: __('Enter email'),
						},
						{
							name: 'role',
							label: __('Role'),
							type: 'select',
							placeholder: __('Select role'),
							options: ['Admin', 'User'],
						},
						{
							name: 'team',
							label: __('Team'),
							type: 'select',
							placeholder: __('Select team'),
							options: teamOptions,
						},
					],
				}"
			/>
		</template>
		<template #actions>
			<Button
				variant="solid"
				:disabled="!newUser.first_name || !newUser.last_name || !newUser.email"
				@click="addUser"
			>
				{{ __('Add') }}
			</Button>
			<Button @click="show = false">{{ __('Cancel') }}</Button>
		</template>
	</Dialog>
</template>

<script setup>
import { reactive, computed } from 'vue'
import { useTeams } from '@/utils/useTeams'
import { useUsers } from '@/utils/useUsers'
import Form from './Form.vue'

const emit = defineEmits(['close'])
const show = computed({
	get: () => true,
	set: (value) => {
		if (!value) {
			emit('close')
		}
	},
})
const newUser = reactive({
	first_name: '',
	last_name: '',
	email: '',
	team: '',
	role: 'User',
})

const teams = useTeams()
const teamOptions = computed(() =>
	[{ label: __('Select Team'), value: '' }].concat(
		teams.list.map((team) => {
			return {
				label: team.team_name,
				value: team.name,
			}
		})
	)
)

const users = useUsers()
function addUser() {
	users.add(newUser).then(() => {
		emit('close')
	})
}
</script>
