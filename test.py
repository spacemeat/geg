from geg import geg

if False:
    s = geg.HierString('-foo-bar-baz-')
    #print (s.render())

    s.markSubStr(9, 12, geg.Style.HIGHLIGHT)
    #print (str(s))
    s.markSubStr(5, 8, [geg.Style.PATH, geg.Style.DIR])
    #print (str(s))
    s.markSubStr(1, 4, geg.Style.PATH)
    #print (str(s))
    print (s.render())


if False:
    fulls = '!foo@bar#baz$'
    s = geg.NestedString(fulls)
    s.markSubStr(1, 12)
    s.nested[0].markSubStr(8, 11)
    s.nested[0].markSubStr(4, 7)
    s.nested[0].markSubStr(0, 3)
    print (fulls)
    print (repr(s))
    print (s.render())


'''
template<class _Ostream, class _Tp>
typename std::enable_if
<
    std::__and_
    <
        std::__not_
        <
            std::is_lvalue_reference
            <
                _Tp
            >
        >,
        std::__is_convertible_to_basic_ostream
        <
            _Ostream
        >,
        std::__is_insertable
        <
            typename std::__is_convertible_to_basic_ostream
            <
                _Tp
            >::__ostream_type,
            const _Tp&,
            void
        >
    >::value,
    typename std::__is_convertible_to_basic_ostream
    <
        _Tp
    >::__ostream_type
>::type std::operator<<(
    _Ostream&&,
    const _Tp&
)'''

errorm = '''‘template<class _Ostream, class _Tp> typename std::enable_if<std::__and_<std::__not_<std::is_lvalue_reference<_Tp> >, std::__is_convertible_to_basic_ostream<_Ostream>, std::__is_insertable<typename std::__is_convertible_to_basic_ostream<_Tp>::__ostream_type, const _Tp&, void>>::value, typename std::__is_convertible_to_basic_ostream<_Tp>::__ostream_type>::type std::operator<<(_Ostream&&, const _Tp&)’'''
#errorm = '''‘std::istream’ {aka ‘std::basic_istream<char>’} is not derived from ‘std::basic_ostream<_CharT, _Traits>’'''
s1 = geg.sanitizeMessage(errorm, True, False)
print('')
s2 = geg.sanitizeMessage(errorm, False, False)
print('')
print(s1)
print('')
print(s1.render())
print('')
print(s2.render())
