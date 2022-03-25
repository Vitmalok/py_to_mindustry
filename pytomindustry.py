import dis

from ptm_types import *
import basic



def _add_names_to_bytes(bytes_):
	zzz = []
	flag = True
	
	for q in bytes_:
		if flag:
			zzz.append(dis.opname[q])
			if q >= 90:
				flag = False
		else:
			zzz.append(q)
			flag = True
	
	return zzz

def translate(compiled, field_of_view='', high_redefined={}, debug_print=False):
	co_code = compiled.co_code
	co_cellvars = compiled.co_cellvars
	co_consts = compiled.co_consts
	co_freevars = compiled.co_freevars
	co_names = compiled.co_names
	co_nlocals = compiled.co_nlocals
	co_stacksize = compiled.co_stacksize
	co_varnames = compiled.co_varnames
	
	named_code = _add_names_to_bytes(co_code)
	
	if debug_print:
		print(*named_code, sep='\n', end='\n\n')
		print(f'co_cellvars:  {co_cellvars}')
		print(f'co_consts:    {co_consts}')
		print(f'co_freevars:  {co_freevars}')
		print(f'co_names:     {co_names}')
		print(f'co_nlocals:   {co_nlocals}')
		print(f'co_stacksize: {co_stacksize}')
		print(f'co_varnames:  {co_varnames}', end='\n\n')
	
	mindustry = []
	stack = []
	
	current_stackvar = Stackvar(field_of_view)
	current_quantvar = Quantvar(field_of_view)
	
	redefined = {}
	basedefined = set(basic.names.keys())
	baserenamed = set(basic.renamed_names.keys())
	
	deferred_jumps = {}
	lines = {}
	
	value_to_return = None
	
	try:
		for opnum in range(0, len(named_code), 2):
			opname = named_code[opnum]
			
			if opname == 'EXTENDED_ARG':
				arg += named_code[opnum + 1] << arg_len*8
				arg_len += 1
				continue
			else:
				arg = named_code[opnum + 1]
				arg_len = 1
			
			lines[opnum] = len(mindustry)
			
			if opnum in deferred_jumps:
				for jump in deferred_jumps[opnum]:
					if len(jump) > 2:
						quantvar = jump[2]
						mindustry.append(['set', quantvar, stack.pop()])
						stack.append(quantvar)
					
					mindustry[jump[0]][jump[1]] = len(mindustry)
			
			match opname:
				case 'NOP':
					pass
				case 'RETURN_VALUE':
					value_to_return = stack.pop()
					
					if field_of_view == '':
						mindustry.append(['end'])
					
					if debug_print:
						print('\n---- RETURN ----\n')
				
				case 'POP_TOP':
					stack.pop()
				case opname if opname.startswith('ROT_'):
					stack.insert({
						'ROT_TWO': -1,
						'ROT_THREE': -2,
						'ROT_FOUR': -3,
						'ROT_N': -arg + 1,
					}[opname], stack.pop())
				case 'DUP_TOP':
					stack.append(stack[-1])
				case 'DUP_TOP_TWO':
					stack.append(stack[-2])
					stack.append(stack[-2])
				
				case 'UNPACK_SEQUENCE':
					stack.extend(reversed(stack.pop()))
				
				case opname if opname.startswith('UNARY_'):
					stack.append(stack.pop().unary_op(mindustry, stack, current_stackvar, opname))
				case opname if opname.startswith('BINARY_') and not opname.endswith('_MATRIX_MULTIPLY'):
					stack.append(stack.pop(-2).binary_op(mindustry, stack, current_stackvar, opname, stack.pop()))
				case opname if opname.startswith('INPLACE_') and not opname.endswith('_MATRIX_MULTIPLY'):
					stack.append(stack.pop(-2).inplace_op(mindustry, stack, current_stackvar, opname, stack.pop()))
				case 'COMPARE_OP':
					stack.append(stack.pop(-2).compare_op(mindustry, stack, current_stackvar, dis.cmp_op[arg], stack.pop()))
				case 'IS_OP':
					stack.append(stack.pop(-2).compare_op(mindustry, stack, current_stackvar, 'is', stack.pop()))
				
				case 'LOAD_CONST':
					stack.append(Const(co_consts[arg]))
				case 'LOAD_NAME':
					if co_names[arg] in redefined:
						stack.append(redefined[co_names[arg]])
					elif co_names[arg] in basedefined:
						stack.append(PyName(co_names[arg], basic.names[co_names[arg]]))
					elif co_names[arg] in baserenamed:
						stack.append(basic.renamed_names[co_names[arg]])
					else:
						stack.append(Name(co_names[arg]))
				case 'LOAD_FAST':
					if co_varnames[arg] in redefined:
						stack.append(field_of_view + '_' + redefined[co_varnames[arg]])
					else:
						stack.append(Name(field_of_view + '_' + co_varnames[arg]))
				case 'LOAD_GLOBAL':
					if co_names[arg] in high_redefined:
						stack.append(high_redefined[co_names[arg]])
					elif co_names[arg] in basedefined:
						stack.append(PyName(co_names[arg], basic.names[co_names[arg]]))
					elif co_names[arg] in baserenamed:
						stack.append(basic.renamed_names[co_names[arg]])
					else:
						stack.append(Name(co_names[arg]))
				case 'LOAD_ATTR':
					pyname = stack.pop()
					
					if hasattr(pyname, 'contained_object'):
						stack.append(getattr(pyname.contained_object, co_names[arg]))
					else:
						stack.append(basic.attrs[co_names[arg]].LOAD_ATTR(
							mindustry, stack, current_stackvar, deferred_jumps, lines, pyname.name
						))
				case 'LOAD_METHOD':
					stack.append(co_names[arg])
				
				case 'STORE_NAME':
					pyname = stack.pop()
					
					if hasattr(pyname, 'contained_object'):
						object_ = PyName(field_of_view + co_names[arg], pyname.contained_object)
					else:
						object_ = Name(field_of_view + co_names[arg])
						mindustry.append(['set', object_, pyname])
					
					redefined[co_names[arg]] = object_
				case 'STORE_FAST':
					...
				case 'STORE_GLOBAL':
					mindustry.append(['set', Name(co_names[arg]), stack.pop()])
				case 'STORE_SUBSCR':
					mindustry.append(['write', stack.pop(-3), stack.pop(-2), stack.pop()])
				case 'STORE_ATTR':
					pyname = stack.pop()
					
					if hasattr(pyname, 'contained_object'):
						setattr(pyname.contained_object, co_names[arg], stack.pop())
					else:
						basic.attrs[co_names[arg]].STORE_ATTR(
							mindustry, stack, current_stackvar, deferred_jumps, lines, pyname.name, stack.pop()
						)
				
				case 'JUMP_IF_NOT_EXC_MATCH':
					raise PyToMindustryError('"JUMP_IF_NOT_EXC_MATCH" operation is not supported yet')
				case opname if opname.startswith('JUMP_') or opname.startswith('POP_JUMP_'):
					pattern = {
						'JUMP_ABSOLUTE': lambda: ['always', 0, 0],
						'JUMP_FORWARD': lambda: ['always', 0, 0],
						'POP_JUMP_IF_FALSE': lambda: ['equal', stack.pop(), 'false'],
						'POP_JUMP_IF_TRUE': lambda: ['notEqual', stack.pop(), 'false'],
						'JUMP_IF_FALSE_OR_POP': lambda: ['equal', stack[-1], 'false'],
						'JUMP_IF_TRUE_OR_POP': lambda: ['notEqual', stack[-1], 'false'],
					}[opname]()
					jump_to = arg*2
					
					if opname == 'JUMP_FORWARD':
						jump_to = opnum + arg*2
					
					if jump_to <= opnum:
						mindustry.append(['jump', lines[jump_to]] + pattern)
					else:
						if opname.startswith('JUMP_IF_'):
							current_quantvar.next()
							mindustry.append(['set', current_quantvar.copy(), stack.pop()])
							jump = (len(mindustry), 1, current_quantvar.copy())
						else:
							jump = (len(mindustry), 1)
						
						if jump_to in deferred_jumps:
							deferred_jumps[jump_to].append(jump)
						else:
							deferred_jumps[jump_to] = [jump]
						
						mindustry.append(['jump', None] + pattern)
				
				case 'CALL_FUNCTION':
					pyname = stack.pop(-arg - 1)
					stack.append(pyname.contained_object.CALL_FUNCTION(
						mindustry, stack, current_stackvar, deferred_jumps, lines, pyname.name, [stack.pop(i) for i in range(-arg, 0)]
					))
				case 'CALL_METHOD':
					pyname = stack.pop(-arg - 2)
					
					if hasattr(pyname, 'contained_object'):
						stack.append(getattr(pyname.contained_object, stack.pop(-arg - 1)).CALL_FUNCTION(
							mindustry, stack, current_stackvar, deferred_jumps, lines, pyname.name, [stack.pop(i) for i in range(-arg, 0)]
						))
					else:
						stack.append(basic.methods[stack.pop(-arg - 1)].CALL_METHOD(
							mindustry, stack, current_stackvar, deferred_jumps, lines, pyname.name, [stack.pop(i) for i in range(-arg, 0)]
						))
				
				case 'GET_ITER':
					pyname = stack.pop()
					stack.append(pyname.contained_object.GET_ITER(
						mindustry, stack, current_stackvar, deferred_jumps, lines, pyname.name
					))
				case 'FOR_ITER':
					pyname = stack.pop()
					stack.append(pyname.contained_object.FOR_ITER(
						mindustry, stack, current_stackvar, deferred_jumps, lines, pyname.name, opnum + arg*2 + 2
					))
				
				case 'MAKE_FUNCTION':
					flags = bin(arg)[2:].rjust(4, '0')
					
					if flags[0] == '1':
						raise PyToMindustryError(f'Function closures is not supported yet')
					if flags[1] == '1':
						raise PyToMindustryError(f'Argument annotations is not supported yet')
					if flags[2] == '1':
						raise PyToMindustryError(f'Keyword argument default values is not supported yet')
					if flags[3] == '1':
						raise PyToMindustryError(f'Argument default values is not supported yet')
					
					name = stack.pop().value
					code = stack.pop().value
					
					class new_function:
						if debug_print:
							print('\n---- ENTER ----\n')
						
						code_object = code
						translated_code = translate(code, name, redefined, debug_print)
						
						def CALL_FUNCTION(mindustry, stack, current_stackvar, deferred_jumps, lines, field_of_view, args):
							translated_code0 = []
							
							for string in new_function.translated_code[0]:
								string_copy = string.copy()
								translated_code0.append(string_copy)
								
								if string_copy[0] == 'jump':
									string_copy[1] += len(mindustry)
							
							for arg_i in range(len(args)):
								mindustry.append(['set', new_function.code_object.co_varnames[arg_i], args[arg_i]])
							
							mindustry.extend(translated_code0)
							
							return new_function.translated_code[1]
					
					stack.append(PyName(name, new_function))
				
				case _:
					raise PyToMindustryError(f'"{opname}" operation is not supported yet')
			
			if debug_print:
				print(stack)
	finally:
		if debug_print and opnum != len(named_code) - 2:
			print()
			print(f'opnum:  {opnum}')
			print(f'opname: {opname}')
			print(f'arg:    {arg}')
			print()
	
	return mindustry, value_to_return

def to_str(translated):
	return '\n'.join(map(lambda x: ' '.join(map(str, x)), translated))

def py_to_mindustry(py_program_text, debug_print=False):
	return to_str(translate(compile(py_program_text, '', 'exec'), debug_print=debug_print)[0])



if __name__ == '__main__':
	with open('py_files/test.py', 'r') as f:
		text = f.read()
	
	print('\n' + py_to_mindustry(text, True))
