


def donuts(count):
    s1 = ("Number of donuts: %d" % (count))
    s2 = "Number of donuts: many"
    if count < 10:
        return s2
    else:
        return s1 


    
    
def both_ends(s):
    if( len(s) < 2) :
        return ""
    else : 
        return s[0:2] + s[-2:]



    
    
def fix_start(s):
    first_letter = s[0]
    partial_str = s[1:]
    asterik_str = partial_str.replace(first_letter, '*')
    return first_letter + asterik_str


def mix_up(a, b):
    a_letters = a[0:2]
    b_letters = b[0:2]
    a_rest = a[2:]
    b_rest = b[2:]
    first_word = b_letters + a_rest
    second_word = a_letters + b_rest
    result = first_word + " " + second_word
    return result


# Provided simple test() function used in main() to print
# what each function returns vs. what it's supposed to return.
def test(got, expected):
  if got == expected:
    prefix = ' OK '
  else:
    prefix = '  X '
  print ('%s got: %s expected: %s') % (prefix, repr(got), repr(expected))


# Provided main() calls the above functions with interesting inputs,
# using test() to check if each result is correct or not.
def main():
  print 'donuts'
  # Each line calls donuts, compares its result to the expected for that call.
  test(donuts(4), 'Number of donuts: 4')
  test(donuts(9), 'Number of donuts: 9')
  test(donuts(10), 'Number of donuts: many')
  test(donuts(99), 'Number of donuts: many')

  print
  print 'both_ends'
  test(both_ends('spring'), 'spng')
  test(both_ends('Hello'), 'Helo')
  test(both_ends('a'), '')
  test(both_ends('xyz'), 'xyyz')

  
  print
  print 'fix_start'
  test(fix_start('babble'), 'ba**le')
  test(fix_start('aardvark'), 'a*rdv*rk')
  test(fix_start('google'), 'goo*le')
  test(fix_start('donut'), 'donut')

  print
  print 'mix_up'
  test(mix_up('mix', 'pod'), 'pox mid')
  test(mix_up('dog', 'dinner'), 'dig donner')
  test(mix_up('gnash', 'sport'), 'spash gnort')
  test(mix_up('pezzy', 'firm'), 'fizzy perm')


# Standard boilerplate to call the main() function.
if __name__ == '__main__':
  main()
